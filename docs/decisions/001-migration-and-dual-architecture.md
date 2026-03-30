# ADR 001: Migration and Dual Architecture

## Context
The legacy system relied heavily on Python for logic, DOCX manipulation (`python-docx`), and UI (`customtkinter`). However, scaling required robust document handling (Apache POI) and enterprise persistence (Spring Data JPA).

## Decision
We migrated the core processing to a Java Spring Boot 3 application.
To maintain backward compatibility and forward scalability, we implemented a **Dual Architecture**:
1. **CLI Mode:** The Spring Boot application can run as a headless CLI. This allows the existing Python GUI to continue operating by spawning the Java JAR via `subprocess.Popen`.
2. **Web Server Mode:** We added a Spring Web Controller to serve a modern HTML/JS interface (`index.html`) and accept multipart document uploads, paving the way to deprecate the Python GUI entirely in the future.
