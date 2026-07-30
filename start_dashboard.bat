@echo off
cd /d "C:\Users\sibap\Downloads\MandiIQ-fda91857aaccd6f0b44bc9a0fc770a9e5ddb22e0"
start /B python -m streamlit run mandi_rdd/dashboard/app.py --server.port 8501 --server.headless true > streamlit.log 2>&1
echo Streamlit started
