# Performance Backlog

This document tracks identified performance bottlenecks and optimization tasks based on load testing results.

## Identified Bottlenecks (2026-04-14)

1.  **Rate Limiting on `POST /add_attendee/`**
    *   **Description:** Concurrency testing is blocked by `429 Too Many Requests` when using more than a few concurrent users.
    *   **Impact:** Cannot measure true DB/App performance for the most critical endpoint.
    *   **Task:** Implement a mechanism to bypass or tune rate limits for load testing (e.g., based on IP or header).

2.  **Login Endpoint Latency**
    *   **Description:** `POST /user_login/` response time jumped to p99=3000ms under 100 concurrent users.
    *   **Impact:** Slower user experience during peak login times.
    *   **Task:** Investigate password hashing cost (it's expected to be slow but maybe too slow under load) and session DB performance.

3.  **Full Load Test (3000 users)**
    *   **Description:** Current baseline is a smoke test with 100 users on SQLite.
    *   **Task:** Run the full 3000-user test on a production-like environment (Docker with PostgreSQL and Redis) once rate limits are handled.
