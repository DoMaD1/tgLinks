[app]
title = Telegram Links
package.name = telegramlinks
package.domain = org.domad1
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.5.0
requirements = python3==3.11.9,hostpython3==3.11.9,kivy==2.3.1,telethon==1.45.0,pyaes,rsa,pyasn1,sqlite3,openssl
orientation = portrait
fullscreen = 0
android.permissions = INTERNET
android.api = 35
android.minapi = 24
android.ndk = 28c
android.archs = arm64-v8a
android.accept_sdk_license = True
android.allow_backup = False
p4a.branch = master
[buildozer]
log_level = 2
warn_on_root = 1
