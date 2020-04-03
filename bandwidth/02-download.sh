#wget \
#     --recursive \
#     --no-clobber \
#     --restrict-file-names=windows \
#     --domains speedtest.net,www.speedtest.net\
#     --no-parent \
#     --ignore-tags=img,link,script \
#     --reject '*.js,*.css,*.ico,*.txt,*.gif,*.jpg,*.jpeg,*.png,*.mp3,*.pdf,*.tgz,*.flv,*.avi,*.mpeg,*.iso' \
#     --header="Accept: text/html" \
#         https://www.speedtest.net/global-index/

wget \
     --recursive \
     --no-clobber \
     --html-extension \
     --convert-links \
     --restrict-file-names=windows \
     --domains speedtest.net \
     --no-parent \
     --reject '*.js,*.css,*.ico,*.txt,*.gif,*.jpg,*.jpeg,*.png,*.mp3,*.pdf,*.tgz,*.flv,*.avi,*.mpeg,*.iso' \
     --ignore-tags=img,link,script \
     --header="Accept: text/html" \
         http://www.speedtest.net/reports/
