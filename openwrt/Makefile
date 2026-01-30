# OpenWRT package Makefile for quectel-5g-tools
#
# To build:
#   1. Clone this repo into openwrt/package/feeds/packages/quectel-5g-tools
#   2. Run: ./scripts/feeds update -a && ./scripts/feeds install quectel-5g-tools
#   3. Run: make menuconfig  (select Network -> quectel-5g-tools)
#   4. Run: make package/quectel-5g-tools/compile

include $(TOPDIR)/rules.mk

PKG_NAME:=quectel-5g-tools
PKG_VERSION:=0.1.0
PKG_RELEASE:=1

PKG_SOURCE_PROTO:=git
PKG_SOURCE_URL:=https://github.com/yourusername/quectel-5g-tools.git
PKG_SOURCE_VERSION:=HEAD
PKG_SOURCE_SUBDIR:=$(PKG_NAME)-$(PKG_VERSION)
PKG_SOURCE:=$(PKG_NAME)-$(PKG_VERSION).tar.gz

PKG_LICENSE:=MIT
PKG_LICENSE_FILES:=LICENSE
PKG_MAINTAINER:=Your Name <you@example.com>

include $(INCLUDE_DIR)/package.mk

define Package/quectel-5g-tools
  SECTION:=net
  CATEGORY:=Network
  TITLE:=Quectel 5G Modem Tools
  DEPENDS:=+python3 +python3-curses +python3-pyserial
  URL:=https://github.com/yourusername/quectel-5g-tools
endef

define Package/quectel-5g-tools/description
  A collection of tools for monitoring and configuring Quectel 5G modems.
  Includes:
    - 5g-info: CLI tool for displaying modem information
    - 5g-monitor: Real-time TUI monitor with signal quality display
    - 5g-http.cgi: CGI script for JSON API
    - at: Simple AT command wrapper
    - force-bands: Band locking utility
endef

define Build/Compile
	# Nothing to compile, pure Python
endef

define Package/quectel-5g-tools/install
	# Install Python library
	$(INSTALL_DIR) $(1)/usr/lib/python3/quectel
	$(INSTALL_DATA) $(PKG_BUILD_DIR)/src/quectel/*.py $(1)/usr/lib/python3/quectel/

	# Install binaries
	$(INSTALL_DIR) $(1)/usr/bin
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/bin/5g-info $(1)/usr/bin/
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/bin/5g-monitor $(1)/usr/bin/
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/bin/at $(1)/usr/bin/quectel-at
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/bin/force-bands $(1)/usr/bin/

	# Install CGI script
	$(INSTALL_DIR) $(1)/www/cgi-bin
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/bin/5g-http.cgi $(1)/www/cgi-bin/

	# Install default config
	$(INSTALL_DIR) $(1)/etc/quectel
	$(INSTALL_CONF) $(PKG_BUILD_DIR)/config/quectel.toml $(1)/etc/quectel/config.toml

	# Install UCI config
	$(INSTALL_DIR) $(1)/etc/config
	$(INSTALL_CONF) $(PKG_BUILD_DIR)/config/quectel.uci $(1)/etc/config/quectel
endef

define Package/quectel-5g-tools/conffiles
/etc/quectel/config.toml
/etc/config/quectel
endef

$(eval $(call BuildPackage,quectel-5g-tools))
