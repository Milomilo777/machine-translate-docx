@echo off
SET OPENAI_API_KEY=your_api_key_here
SET MARIADB_PASSWORD=your_db_password
start javaw -jar target/translation-robot.jar
echo SMTV Web Server started at http://localhost:8080
