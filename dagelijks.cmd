@echo off
rem Dagelijkse run: checks draaien en het dashboard opnieuw renderen naar HTML.
rem Aangeroepen door de Windows-taak "CHO-KENNIS kwaliteitscheck". Uitvoer in data\dagelijks.log.
cd /d "%~dp0"
if not exist data mkdir data
set PYTHONIOENCODING=utf-8
echo ==== %date% %time% >> data\dagelijks.log
"C:\Python314\python.exe" kwaliteit.py >> data\dagelijks.log 2>&1
"C:\Python314\python.exe" -m jupyter nbconvert --to html --execute --no-input dashboard.ipynb --output dashboard.html >> data\dagelijks.log 2>&1
