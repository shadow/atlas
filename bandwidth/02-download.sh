wget \
     --recursive \
     --no-clobber \
     --restrict-file-names=windows \
     --domains speedtest.net,www.speedtest.net\
     --no-parent \
     --ignore-tags=img,link,script \
     --reject '*.js,*.css,*.ico,*.txt,*.gif,*.jpg,*.jpeg,*.png,*.mp3,*.pdf,*.tgz,*.flv,*.avi,*.mpeg,*.iso' \
     --header="Accept: text/html" \
         https://www.speedtest.net/global-index/



# This is disabled for now. This was to fetch city data. It's 2020 now and
# speedtest.net has changed there website juuuust enough since 2018 that it's
# going tp be harder for me to figure out how to automatically fetch and parse
# city data from them than for me to just describe how to manually fetch it
# yourself. Hopefully I have *something* to help parse ...

#wget \
#     --recursive \
#     --no-clobber \
#     --html-extension \
#     --convert-links \
#     --restrict-file-names=windows \
#     --domains speedtest.net \
#     --no-parent \
#     --reject '*.js,*.css,*.ico,*.txt,*.gif,*.jpg,*.jpeg,*.png,*.mp3,*.pdf,*.tgz,*.flv,*.avi,*.mpeg,*.iso' \
#     --ignore-tags=img,link,script \
#     --header="Accept: text/html" \
#         http://www.speedtest.net/reports/
