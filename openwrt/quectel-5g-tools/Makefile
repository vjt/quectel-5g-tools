# OpenWRT package Makefile for quectel-5g-tools
#
# To build as a local feed:
#   1. Clone this repo somewhere persistent on the build host
#   2. Add to <openwrt>/feeds.conf:
#        src-link custom /path/to/feeds-local
#   3. Symlink this package dir into feeds-local/:
#        ln -s /path/to/quectel-5g-tools/openwrt/quectel-5g-tools \
#              <openwrt>/feeds-local/quectel-5g-tools
#   4. ./scripts/feeds update custom && ./scripts/feeds install -a -p custom
#   5. make menuconfig (Network -> quectel-5g-tools)
#   6. make package/quectel-5g-tools/compile

include $(TOPDIR)/rules.mk

PKG_NAME:=quectel-5g-tools
PKG_VERSION:=1.3.0
PKG_RELEASE:=1

PKG_SOURCE_PROTO:=git
PKG_SOURCE_URL:=https://github.com/vjt/quectel-5g-tools.git
PKG_SOURCE_VERSION:=HEAD
PKG_SOURCE_SUBDIR:=$(PKG_NAME)-$(PKG_VERSION)
PKG_SOURCE:=$(PKG_NAME)-$(PKG_VERSION).tar.gz

PKG_LICENSE:=MIT
PKG_LICENSE_FILES:=LICENSE
PKG_MAINTAINER:=Marcello Barnaba <mbarnaba@meta.com>

include $(INCLUDE_DIR)/package.mk

define Package/quectel-5g-tools
  SECTION:=net
  CATEGORY:=Network
  TITLE:=Quectel 5G Modem Tools
  DEPENDS:=+lua +luaposix +libuci-lua +luci-lib-jsonc +modemmanager +curl
  URL:=https://github.com/vjt/quectel-5g-tools
endef

define Package/quectel-5g-tools/description
  A collection of Lua tools for monitoring and configuring Quectel 5G modems.
  Designed for GL.iNET routers with Quectel RM520N-GL modems.
  Includes:
    - 5g-info: CLI tool for displaying modem information
    - 5g-monitor: Real-time TUI monitor with signal quality display and beeps
    - 5g-led-bars: procd service driving the GL-X3000 5G signal LEDs from RSRP
    - 5g-watchdog: procd service that detects NSA NR SCG drops via mmcli
      and forces a re-attach (disable/enable, mode-toggle fallback).
    - at: Simple AT command wrapper
    - 5g-lock: Band and cell locking utility
    - Prometheus collector for prometheus-node-exporter-lua
endef

# This is a pure-script package — there's no top-level Makefile in the
# source tree to drive a build. Override the default Build/Compile (which
# would invoke `make` in PKG_BUILD_DIR and fail with "no Makefile found")
# with a no-op so the build phase succeeds and Package/install runs.
define Build/Compile
endef

define Package/quectel-5g-tools/install
	# Install Lua library
	$(INSTALL_DIR) $(1)/usr/lib/lua/quectel
	$(INSTALL_DATA) $(PKG_BUILD_DIR)/lua/quectel/*.lua $(1)/usr/lib/lua/quectel/

	# Install Prometheus collectors (glob: quectel.lua + quectel-watchdog.lua + any added later)
	$(INSTALL_DIR) $(1)/usr/lib/lua/prometheus-collectors
	$(INSTALL_DATA) $(PKG_BUILD_DIR)/lua/prometheus-collectors/*.lua $(1)/usr/lib/lua/prometheus-collectors/

	# Install binaries
	$(INSTALL_DIR) $(1)/usr/bin
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/bin/5g-info $(1)/usr/bin/
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/bin/5g-monitor $(1)/usr/bin/
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/bin/5g-led-bars $(1)/usr/bin/
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/bin/5g-watchdog $(1)/usr/bin/
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/bin/at $(1)/usr/bin/quectel-at
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/bin/5g-lock $(1)/usr/bin/
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/bin/modem-debug $(1)/usr/bin/

	# Install procd init scripts
	$(INSTALL_DIR) $(1)/etc/init.d
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/etc/init.d/5g-led-bars $(1)/etc/init.d/
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/etc/init.d/5g-watchdog $(1)/etc/init.d/

	# Tell ModemManager to skip the Quectel USB AT/DIAG/NMEA/AT2 ports
	# (/dev/ttyUSB0..3). The patched /etc/hotplug.d/tty/25-modemmanager-tty
	# (see x3000/prepare.sh in the OpenWrt fork) honours this list and
	# never reports those ports to MM, leaving them free for our own
	# 5g-info / 5g-monitor / 5g-lock / 5g-led-bars helpers.
	$(INSTALL_DIR) $(1)/etc/modemmanager
	$(INSTALL_DATA) $(PKG_BUILD_DIR)/config/mm-ignore-tty $(1)/etc/modemmanager/ignore-tty

	# Install uci-defaults (each runs once on first boot; see file headers).
	# Glob so new files added to etc/uci-defaults/ in the source tree get
	# picked up without having to remember to update the install recipe.
	$(INSTALL_DIR) $(1)/etc/uci-defaults
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/etc/uci-defaults/* $(1)/etc/uci-defaults/

	# Install UCI config
	$(INSTALL_DIR) $(1)/etc/config
	$(INSTALL_CONF) $(PKG_BUILD_DIR)/config/quectel.uci $(1)/etc/config/quectel
endef

define Package/quectel-5g-tools/conffiles
/etc/config/quectel
endef

$(eval $(call BuildPackage,quectel-5g-tools))
