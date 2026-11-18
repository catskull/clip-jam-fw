#!/bin/sh
# Convert any video to an AMV the Clip Jam's video.ap can (hopefully) play.
#   to_amv.sh INPUT OUTPUT.amv [WxH] [THRESHOLD]
# The OLED driver only lights pixels whose RGB565 value is exactly 0xFFFF, so the
# picture is thresholded to pure black/white and encoded at high JPEG quality to
# keep the whites at exactly 255 after decoding.
set -e
in=$1; out=$2; size=${3:-128x64}; th=${4:-128}
w=${size%x*}; h=${size#*x}
ffmpeg -hide_banner -loglevel warning -y -i "$in" \
  -vf "scale=${w}:${h}:force_original_aspect_ratio=decrease,pad=${w}:${h}:(ow-iw)/2:(oh-ih)/2,fps=15,format=gray,lutyuv=y='if(gt(val,${th}),255,0)',format=yuvj420p" \
  -c:v amv -q:v 2 -strict -1 \
  -c:a adpcm_ima_amv -ac 1 -ar 22050 -block_size 1470 \
  "$out"
