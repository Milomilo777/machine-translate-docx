@echo off
REM Dummy build script to satisfy asset synchronization
echo Building the Java Backend using Maven...
mvn clean package -DskipTests
echo Build complete!
pause