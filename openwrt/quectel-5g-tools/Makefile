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
PKG_VERSION:=1.0.0
PKG_RELEASE:=11

PKG_SOURCE_PROTO:=git
PKG_SOURCE_URL:=https://github.com/vjt/quectel-5g-tools.git
PKG_SOURCE_VERSION:=HEAD
PKG_SOURCE_SUBDIR:=$(PKG_NAME)-$(PKG_VERSION)
PKG_SOURCE:=$(PKG_NAME)-$(PKG_VERSION).tar.gz

PKG_LICENSE:=MIT
PKG_LICENSE_FILES:=LICENSE
PKG_MAINTAINER:=Marcello Barnaba <mbarnaba@meta.com>

PKG_BUILD_DEPENDS:=libmbim glib2

include $(INCLUDE_DIR)/package.mk

define Package/quectel-5g-tools
  SECTION:=net
  CATEGORY:=Network
  TITLE:=Quectel 5G Modem Tools
  DEPENDS:=+lua +luaposix +libuci-lua +libmbim +glib2
  URL:=https://github.com/vjt/quectel-5g-tools
endef

define Package/quectel-5g-tools/description
  A collection of Lua tools for monitoring and configuring Quectel 5G modems.
  Designed for GL.iNET routers with Quectel RM520N-GL modems.
  Includes:
    - 5g-info: CLI tool for displaying modem information
    - 5g-monitor: Real-time TUI monitor with signal quality display and beeps
    - 5g-led-bars: procd service driving the GL-X3000 5G signal LEDs from RSRP
    - mbim-watchdog: procd daemon that watches MBIM Connect indications and
      reconnects via `ifup` when the carrier deactivates the data session
    - at: Simple AT command wrapper
    - 5g-lock: Band and cell locking utility
    - Prometheus collector for prometheus-node-exporter-lua
endef

# libmbim + glib2 must be staged before this Build/Compile runs.
# Tried `+$(MAKE) -C $(TOPDIR) package/libmbim/compile` from a Build/Configure
# recipe — fails fast with no useful diagnostic (sub-make recursion inside a
# package compile is not honoured). The reliable way is to have the builder
# bootstrap script compile those deps first; we configure that via the repo's
# `pre_compile_deps: [libmbim, glib2]` field in the openwrt-builder config.
# Keep PKG_BUILD_DEPENDS for documentation + correct dep ordering when this
# package is built from the buildroot top.

# Explicit -I/-l paths beat $(PKG_CONFIG) substitution: the SDK's
# pkg-config wrapper expects STAGING_DIR_HOST + PKG_CONFIG_PATH to be
# set in the environment at the point of `make package/.../compile`,
# and that's not guaranteed when the build is triggered via the
# top-level `make` from the builder bootstrap script. Hardcoding the
# include and library names sidesteps the wrapper entirely.
define Build/Compile
	$(TARGET_CC) $(TARGET_CFLAGS) $(TARGET_CPPFLAGS) \
		-I$(STAGING_DIR)/usr/include/libmbim-glib \
		-I$(STAGING_DIR)/usr/include/glib-2.0 \
		-I$(STAGING_DIR)/usr/lib/glib-2.0/include \
		-o $(PKG_BUILD_DIR)/src/mbim-watchdog \
		$(PKG_BUILD_DIR)/src/mbim-watchdog.c \
		$(TARGET_LDFLAGS) \
		-lmbim-glib -lgio-2.0 -lgobject-2.0 -lglib-2.0
endef

define Package/quectel-5g-tools/install
	# Install Lua library
	$(INSTALL_DIR) $(1)/usr/lib/lua/quectel
	$(INSTALL_DATA) $(PKG_BUILD_DIR)/lua/quectel/*.lua $(1)/usr/lib/lua/quectel/

	# Install Prometheus collector
	$(INSTALL_DIR) $(1)/usr/lib/lua/prometheus-collectors
	$(INSTALL_DATA) $(PKG_BUILD_DIR)/lua/prometheus-collectors/quectel.lua $(1)/usr/lib/lua/prometheus-collectors/

	# Install binaries
	$(INSTALL_DIR) $(1)/usr/bin
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/bin/5g-info $(1)/usr/bin/
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/bin/5g-monitor $(1)/usr/bin/
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/bin/5g-led-bars $(1)/usr/bin/
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/bin/at $(1)/usr/bin/quectel-at
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/bin/5g-lock $(1)/usr/bin/
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/bin/modem-debug $(1)/usr/bin/
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/src/mbim-watchdog $(1)/usr/bin/

	# Install procd init scripts
	$(INSTALL_DIR) $(1)/etc/init.d
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/etc/init.d/5g-led-bars $(1)/etc/init.d/
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/etc/init.d/mbim-watchdog $(1)/etc/init.d/

	# Install uci-defaults (runs once on first boot; see file header)
	$(INSTALL_DIR) $(1)/etc/uci-defaults
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/etc/uci-defaults/95-5g-led-bars $(1)/etc/uci-defaults/

	# Install UCI config
	$(INSTALL_DIR) $(1)/etc/config
	$(INSTALL_CONF) $(PKG_BUILD_DIR)/config/quectel.uci $(1)/etc/config/quectel
endef

define Package/quectel-5g-tools/conffiles
/etc/config/quectel
endef

$(eval $(call BuildPackage,quectel-5g-tools))
