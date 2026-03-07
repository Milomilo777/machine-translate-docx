# The Enterprise Testing Matrix

This project adheres to a 10-layer Quality Assurance and Security strategy to ensure absolute robustness.

## Layers

1. **JUnit 5:** The foundation for all unit and component tests.
2. **JaCoCo:** Line-by-line code coverage analysis.
3. **Mockito:** Aggressive mocking of the `TranslationEngine` to prevent accidental external network/API usage during tests.
4. **Jqwik (Property/Fuzzing):** Randomized stress testing (e.g., negative tokens, massive strings, ZWNJ unicode fuzzing) to guarantee exception-safety without hardcoded inputs.
5. **PITest (Mutation):** Alters the bytecode during testing to verify that tests actually fail when logic is compromised.
6. **WireMock:** HTTP Contract testing to simulate exact JSON responses from OpenAI/DeepL to verify our Jackson object mappers.
7. **SpotBugs (SAST):** Static Application Security Testing analyzing bytecode for null pointers, exposed internal representations, and memory leaks.
8. **ArchUnit (Architecture):** Asserts the fitness of the domain (e.g., Services cannot depend on Controllers, prohibiting cyclic dependencies).
9. **OWASP (Supply Chain):** Audits dependencies against the NVD (National Vulnerability Database) for known CVEs.
10. **Log Integrity Sentinels:** E2E tests specifically asserting that stdout contracts (used by the Python GUI) remain unbroken.

## Execution Commands

### Standard Fast Verification
Runs JUnit, JaCoCo, ArchUnit, and WireMock.
```bash
mvn clean test jacoco:report
```

### Mutation Testing (Profiled)
Runs PITest on core logic only. Bound to 2 threads to prevent CPU starvation.
```bash
mvn org.pitest:pitest-maven:mutationCoverage -P mutation-testing
```

### Supply Chain Audit (Profiled)
Downloads NVD databases and scans `pom.xml` dependencies.
```bash
mvn dependency-check:check -P security-scan
```

### SAST Analysis (Non-Blocking)
Runs SpotBugs without failing the build. Use `mvn spotbugs:gui` to view the report.
```bash
mvn spotbugs:check
```
