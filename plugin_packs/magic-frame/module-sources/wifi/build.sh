#!/bin/sh
# module.js = qrcode-generator (MIT, verkleinert) + module.src.js, beides in einer Funktion
set -e
cd "$(dirname "$0")"
{
  echo "/* qrcode-generator 1.4.4, Copyright (c) 2009 Kazuhiko Arase, MIT license, https://github.com/kazuhikoarase/qrcode-generator */"
  echo "(function () {"
  npx -y terser@5.31.0 lib/qrcode-generator.js --compress --mangle
  echo ""
  cat module.src.js
  echo "})();"
} > module.js
