@echo off
cd backend
python -m pip install --upgrade pip
pip install -r requirements.txt
cd ..
echo Backend installation complete.
pause
