@echo off
:: Set your environment variables here
SET OPENAI_API_KEY=your_key_here
SET MARIADB_URL=jdbc:mariadb://localhost:3306/translation
SET MARIADB_USER=root
SET MARIADB_PASSWORD=

:: Run the Fat JAR
java -jar target/translation-robot.jar %1 %2
