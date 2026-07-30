cd /c/Users/sibap/Downloads/MandiIQ-fda91857aaccd6f0b44bc9a0fc770a9e5ddb22e0
# Add mandiq-effects.js + scrollbar removal to landing/index.html (before </head>)
sed -i 's|</head>|\n<script src="..\\/docs\\/mandiq-effects.js"><\\/script>\n<style>\\n::-webkit-scrollbar{display:none}\\nhtml{scrollbar-width:none;-ms-overflow-style:none}\\n<\\/style>\\n</head>|' landing/index.html
echo "Done: landing/index.html"

# Add scrollbar removal to docs/index.html (before </head>)
if grep -q 'scrollbar-width' docs/index.html; then
    echo "Already has scrollbar CSS"
else
    sed -i 's|</style>|\n::-webkit-scrollbar{display:none}\nhtml{scrollbar-width:none;-ms-overflow-style:none}\n</style>|' docs/index.html
    echo "Added scrollbar CSS to docs/index.html"
fi