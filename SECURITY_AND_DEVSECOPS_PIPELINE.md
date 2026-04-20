# Security Architecture & DevSecOps Roadmap: Reference Agent

This document summarizes the multi-layered security framework and automated DevSecOps pipelines integrated into the **Reference Agent** ecosystem. This context is optimized for generating detailed security-focused architecture and sequence diagrams.

---

## 1. Identity & Access Security (The Authentication Perimeter)
The system implements a **Zero-Trust Identity model** to ensure that only verified researchers can access sensitive extraction engines.

*   **Credential Hardening**: Passwords are never stored in plain text; they are hashed with **Bcrypt** using a unique per-user salt.
*   **Two-Factor Verification (2FA)**: A mandatory **MFA sequence** using SMTP-delivered OTP (6-digit temporal codes) is required for both account activation and login verification.
*   **Stateless Identity**: Secure **JWT (JSON Web Tokens)** are issued upon successful MFA verification. These use **HS256** signatures with a high-entropy secret key stored in protected environment variables.
*   **Client-Side Protection**: Tokens are securely stored and automatically attached to every API request via **Axios interceptors**, with automated logic to handle token expiration (401 Unauthorized status).

---

## 2. Input Security (The Data Ingestion Firewall)
PDF and Word documents are treated as "high-risk" inputs. The system implements the following "Shift-Left" security checks:

*   **Pydantic Schema Validation**: Every API payload is strictly validated against schemas to prevent Injection (SQL/NoSQL) and Buffer Overflow attacks.
*   **File Sanitization (CDR Context)**: Implementation of Content Disarm and Reconstruction principles, stripping potentially malicious macros or active scripts from `.docx` and `.pdf` files before parsing.
*   **Rate Limiting & Throttling**: The FastAPI backend implements peak-rate limits to protect against Denial of Service (DoS) attacks on the computationally expensive LLM/NER engines.

---

## 3. Persistent Information Assurance (Data Privacy)
To protect unpublished Research Intellectual Property (IP):

*   **Local-First AI Execution**: By orchestrating **Ollama (Local LLM)**, the system ensures that the most sensitive research data (the paper itself) never leaves the user's machines for cloud-based training.
*   **Secure Environment Storage**: Sensitive API keys for enrichment (CrossRef, OpenAlex) and SMTP credentials are isolated in a `.env` file, excluded from version control via `.gitignore`.

---

## 4. DevSecOps CI/CD Pipeline (The Automation Layer)
A "Shift-Left" security strategy is executed automatically on every code push to the main branch via GitHub Actions.

### A. Secret Scanning Pipeline
*   **Tool**: `trufflesecurity/trufflehog`
*   **Action**: Scans the entire repository history for leaked API keys, PEM files, and hardcoded credentials.
*   **Failure State**: Blocks the merge if any secret is detected.

### B. Static Application Security Testing (SAST)
*   **Tool**: `Bandit` (for Python/FastAPI)
*   **Action**: Analyzes source code for common security vulnerabilities (e.g., use of `eval`, insecure random number generators, or improper hardcoded paths).
*   **Tool**: `ESLint` (for Next.js/React)
*   **Action**: Ensures code quality and prevents insecure JSX/JS patterns.

### C. Logic & Integrity Verification
*   **Tool**: `Pytest`
*   **Action**: Automated execution of unit tests to ensure that security logic (e.g., JWT signing, OTP expiration) remains intake and hasn't been broken by new feature development.

---

## 5. Security Visualization Sequence
When a user uploads a paper:
1.  **Auth Check**: Axios interceptor verifies JWT validity.
2.  **Ingestion Check**: FastAPI Pydantic models validate the multi-part file upload.
3.  **Sanitization Check**: Processor strips active elements.
4.  **Privacy Check**: Local NER/LLM is triggered (No cloud exit).
5.  **Audit Log**: The system logs the event for administrative review.
0