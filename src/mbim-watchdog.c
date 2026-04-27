/*
 * mbim-watchdog: subscribe to MBIM BASIC_CONNECT/CONNECT indications via
 * mbim-proxy and run `ifup <iface>` whenever the modem reports the data
 * session as deactivated.
 *
 * Why this exists: OpenWrt's `proto mbim` (umbim + mbim.sh) does a one-shot
 * connect and exits. cdc_mbim keeps the netdev UP regardless of what the
 * carrier does to the PDN, so a carrier-side deactivation (idle timer,
 * RAT change, session refresh) leaves us with a stale IP and no traffic
 * until something external reconnects. ModemManager covers this on stock
 * GL.iNet firmware; we stripped MM, so we cover it here.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <glib.h>
#include <glib-unix.h>
#include <gio/gio.h>
#include <libmbim-glib.h>

static GMainLoop *loop;
static MbimDevice *device;
static gchar *opt_device = NULL;
static gchar *opt_iface = NULL;
static gint64 last_ifup_us;
static gboolean ifup_pending = FALSE;

static void open_device (void);

static GOptionEntry option_entries[] = {
    { "device", 'd', 0, G_OPTION_ARG_FILENAME, &opt_device,
      "MBIM control device (default /dev/wwan0mbim0)", "PATH" },
    { "iface", 'i', 0, G_OPTION_ARG_STRING, &opt_iface,
      "OpenWrt netifd interface to ifup on disconnect (default wwan)", "NAME" },
    { NULL }
};

#define IFUP_COOLDOWN_USEC (30 * G_USEC_PER_SEC)

/*
 * netifd's `proto mbim` opens /dev/wwan0mbim0 directly (no mbim-proxy),
 * so we must release the device before invoking ifup, otherwise umbim's
 * caps/connect calls collide on the cdc-wdm endpoint. Sequence:
 *   1. close MBIM device (drops mbim-proxy's last client → proxy releases cdc-wdm)
 *   2. spawn `ifup <iface>` synchronously (umbim runs the full setup)
 *   3. re-open MBIM device through mbim-proxy and resume listening
 */
static gboolean
do_ifup_and_reopen (gpointer user_data)
{
    gchar *argv[] = { "/sbin/ifup", opt_iface, NULL };
    GError *error = NULL;
    gint exit_status = 0;

    g_message ("Running: ifup %s", opt_iface);
    if (!g_spawn_sync (NULL, argv, NULL,
                       G_SPAWN_STDOUT_TO_DEV_NULL | G_SPAWN_STDERR_TO_DEV_NULL,
                       NULL, NULL, NULL, NULL, &exit_status, &error)) {
        g_warning ("ifup spawn failed: %s", error->message);
        g_clear_error (&error);
    } else if (exit_status != 0) {
        g_warning ("ifup exited with status %d", exit_status);
    }

    ifup_pending = FALSE;
    open_device ();
    return G_SOURCE_REMOVE;
}

static void
trigger_ifup (void)
{
    if (ifup_pending) {
        g_message ("ifup already in flight, skipping");
        return;
    }

    gint64 now = g_get_monotonic_time ();
    if (now - last_ifup_us < IFUP_COOLDOWN_USEC) {
        g_message ("ifup cooldown active, skipping");
        return;
    }
    last_ifup_us = now;
    ifup_pending = TRUE;

    if (device) {
        mbim_device_close_force (device, NULL);
        g_object_unref (device);
        device = NULL;
    }

    g_idle_add (do_ifup_and_reopen, NULL);
}

static void
on_indicate_status (MbimDevice *dev, MbimMessage *message, gpointer user_data)
{
    if (mbim_message_indicate_status_get_service (message) != MBIM_SERVICE_BASIC_CONNECT)
        return;
    if (mbim_message_indicate_status_get_cid (message) != MBIM_CID_BASIC_CONNECT_CONNECT)
        return;

    guint32 session_id = 0;
    MbimActivationState activation_state = MBIM_ACTIVATION_STATE_UNKNOWN;
    const MbimUuid *context_type = NULL;
    guint32 nw_error = 0;
    GError *error = NULL;

    if (!mbim_message_connect_notification_parse (message,
                                                  &session_id,
                                                  &activation_state,
                                                  NULL,
                                                  NULL,
                                                  &context_type,
                                                  &nw_error,
                                                  &error)) {
        g_warning ("Failed to parse Connect notification: %s",
                   error ? error->message : "unknown");
        g_clear_error (&error);
        return;
    }

    g_message ("Connect indication: session=%u state=%s context=%s nw_error=%u",
               session_id,
               mbim_activation_state_get_string (activation_state),
               mbim_context_type_get_string (mbim_uuid_to_context_type (context_type)),
               nw_error);

    if (activation_state == MBIM_ACTIVATION_STATE_DEACTIVATED &&
        mbim_uuid_to_context_type (context_type) == MBIM_CONTEXT_TYPE_INTERNET) {
        g_message ("Internet context deactivated, triggering ifup %s", opt_iface);
        trigger_ifup ();
    }
}

static void
on_open_ready (MbimDevice *dev, GAsyncResult *res, gpointer user_data)
{
    GError *error = NULL;
    if (!mbim_device_open_full_finish (dev, res, &error)) {
        g_critical ("MBIM open failed: %s", error->message);
        g_clear_error (&error);
        g_main_loop_quit (loop);
        return;
    }
    g_message ("MBIM device open via proxy; listening for Connect indications");
    g_signal_connect (dev,
                      MBIM_DEVICE_SIGNAL_INDICATE_STATUS,
                      G_CALLBACK (on_indicate_status),
                      NULL);
}

static void
on_device_new_ready (GObject *src, GAsyncResult *res, gpointer user_data)
{
    GError *error = NULL;
    device = mbim_device_new_finish (res, &error);
    if (!device) {
        g_critical ("MbimDevice creation failed: %s", error->message);
        g_clear_error (&error);
        g_main_loop_quit (loop);
        return;
    }
    mbim_device_open_full (device,
                           MBIM_DEVICE_OPEN_FLAGS_PROXY,
                           30,
                           NULL,
                           (GAsyncReadyCallback) on_open_ready,
                           NULL);
}

static void
open_device (void)
{
    GFile *file = g_file_new_for_path (opt_device);
    mbim_device_new (file, NULL, on_device_new_ready, NULL);
    g_object_unref (file);
}

static gboolean
on_signal (gpointer user_data)
{
    g_message ("Caught signal, exiting");
    g_main_loop_quit (loop);
    return G_SOURCE_REMOVE;
}

int
main (int argc, char *argv[])
{
    GOptionContext *option_ctx = g_option_context_new ("- MBIM connect-state watchdog");
    g_option_context_add_main_entries (option_ctx, option_entries, NULL);

    GError *error = NULL;
    if (!g_option_context_parse (option_ctx, &argc, &argv, &error)) {
        g_printerr ("option parsing failed: %s\n", error->message);
        g_clear_error (&error);
        g_option_context_free (option_ctx);
        return 1;
    }
    g_option_context_free (option_ctx);

    if (!opt_device)
        opt_device = g_strdup ("/dev/wwan0mbim0");
    if (!opt_iface)
        opt_iface = g_strdup ("wwan");

    loop = g_main_loop_new (NULL, FALSE);
    g_unix_signal_add (SIGINT,  on_signal, NULL);
    g_unix_signal_add (SIGTERM, on_signal, NULL);

    open_device ();

    g_main_loop_run (loop);

    if (device) {
        mbim_device_close_force (device, NULL);
        g_object_unref (device);
    }
    g_main_loop_unref (loop);
    g_free (opt_device);
    g_free (opt_iface);
    return 0;
}
