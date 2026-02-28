# Demo Scenario: Database Category Progression

**Goal:** Demonstrate how LeadSync AI understands progression in development for tasks with the same category (`database`), including context retrieval, ruleset application, and precedent-based reasoning.

**Setup:** Create 10 Jira tickets in sequence. Each ticket is marked with label `database`. When you create **Ticket 11** (the demo ticket), LeadSync should retrieve the last 10 completed tickets and show progression context.

---

## Ticket 1: User Identity & Schema Foundation

**Summary:** `Implement user identity schema with PostgreSQL migrations`

**Description:**
```
CONTEXT
We're building the core user management layer for the platform. This is the foundation for all authentication and authorization features.

REQUIREMENTS
- Create users table with id, email, password_hash, created_at, updated_at columns
- Add email uniqueness constraint
- Create database migration with rollback capability
- Set up password hashing utility (bcrypt)

CONSTRAINTS
- Must support future authentication methods (OAuth, SAML)
- Zero-downtime migrations required
- Must handle concurrent user creation safely

ACCEPTANCE CRITERIA
- Migration runs and rolls back cleanly
- Users table passes 5000+ concurrent inserts
- Email constraint prevents duplicates
- Password hashing verified in tests
```

**Label:** `database`
**Status:** Done
**Description notes:** Full context — use as template for subsequent tickets

---

## Ticket 2: User Metadata Extension

**Summary:** `Add user profile metadata table (full_name, avatar_url, bio)`

**Description:**
```
Extend user identity schema from LEADS-1 by adding profile metadata. Keep tight coupling of user and profile data.

Add columns: full_name, avatar_url, bio to users table (per schema minimalism rule — < 3 columns, extend existing table).

ACCEPTANCE CRITERIA
- Migration is additive (backward compatible)
- Data integrity maintained
- Tests pass
```

**Label:** `database`
**Status:** Done

---

## Ticket 3: User Roles & Permissions Table

**Summary:** `Create roles and permissions schema with junction tables`

**Description:**
```
Implement role-based access control (RBAC) foundation. New entity with own lifecycle (roles are shared across users, managed independently).

Create:
- roles table (id, name, description)
- permissions table (id, name, description, resource)
- user_roles junction table (user_id, role_id, created_at)
- role_permissions junction table (role_id, permission_id)

ACCEPTANCE CRITERIA
- Junction tables created (per rule: relationship data always gets dedicated table)
- Indexes on foreign keys
- No direct user->permission queries needed (always through roles)
- Tests pass
```

**Label:** `database`
**Status:** Done

---

## Ticket 4: Add Audit Logging Table

**Summary:** `Implement audit logging for user and role changes`

**Description:**
```
Track all mutations to users, roles, and permissions for compliance and debugging.

Create audit_logs table:
- id, action, entity_type, entity_id, old_value, new_value, created_by, created_at

ACCEPTANCE CRITERIA
- Captures user creation, role assignment, permission changes
- Indexed by entity_id and created_at for fast queries
- Data retained for 12 months
- Tests pass
```

**Label:** `database`
**Status:** Done

---

## Ticket 5: Add Organizations & Teams Schema

**Summary:** `Create organizations and teams hierarchy for multi-tenant support`

**Description:**
```
Support multiple organizations with team structures. New entities (organizations manage teams, teams manage users).

Create:
- organizations table (id, name, slug, created_at)
- teams table (id, org_id, name, description, created_at)
- team_members junction table (team_id, user_id, role_in_team, created_at)

ACCEPTANCE CRITERIA
- Org/team hierarchy intact
- Foreign key constraints enforce referential integrity
- Indexes on org_id and team_id
- Tests pass
```

**Label:** `database`
**Status:** Done

---

## Ticket 6: Add Org-Scoped Audit Logging

**Summary:** `Extend audit logging to track organization-level changes`

**Description:**
```
Track organization creation, team changes, membership mutations.

Extend audit_logs table with org_id, team_id columns (< 3 columns, extend existing table).

ACCEPTANCE CRITERIA
- All org and team mutations logged
- Queries can filter by org_id
- Backward compatible with user-level audit logs
- Tests pass
```

**Label:** `database`
**Status:** Done

---

## Ticket 7: Add User Session & Auth Token Schema

**Summary:** `Implement session and token storage for authentication`

**Description:**
```
Support stateful sessions and JWT token management. New entity — tokens have independent lifecycle from users.

Create:
- sessions table (id, user_id, created_at, expires_at, ip_address)
- auth_tokens table (id, user_id, token_hash, scope, created_at, expires_at, revoked_at)

ACCEPTANCE CRITERIA
- Sessions expire automatically
- Tokens can be revoked early
- Token hashes indexed for fast lookups
- Tests pass
```

**Label:** `database`
**Status:** Done

---

## Ticket 8: Add Email Verification Flow Schema

**Summary:** `Create email verification and change request tables`

**Description:**
```
Support email verification on signup and email change verification flow.

Create:
- email_verifications table (id, user_id, email, verification_code, expires_at, verified_at)
- email_changes_pending table (id, user_id, new_email, verification_code, expires_at)

ACCEPTANCE CRITERIA
- Verification codes are single-use
- Codes expire after 24 hours
- Verified emails linked back to users table
- Tests pass
```

**Label:** `database`
**Status:** Done

---

## Ticket 9: Add Device Tracking for Security

**Summary:** `Implement device and login tracking for security monitoring`

**Description:**
```
Track devices and login attempts for anomaly detection and security audits.

Create:
- devices table (id, user_id, device_name, device_type, trusted, created_at, last_seen_at)
- login_attempts table (id, user_id, device_id, ip_address, status (success|failed), created_at)

ACCEPTANCE CRITERIA
- Login attempts indexed by user_id and created_at
- Devices can be marked trusted/untrusted
- Failed logins retained for 90 days
- Tests pass
```

**Label:** `database`
**Status:** Done

---

## Ticket 10: Add OAuth Provider Credentials Storage

**Summary:** `Create OAuth provider integration schema`

**Description:**
```
Store OAuth provider credentials and linked identities for third-party auth (Google, GitHub, etc.).

Create:
- oauth_providers table (id, provider_name, client_id, client_secret_encrypted, created_at)
- oauth_identities table (id, user_id, provider_id, provider_user_id, email_from_provider, created_at)

ACCEPTANCE CRITERIA
- Secrets are encrypted in storage
- Users can link/unlink multiple OAuth providers
- Foreign keys enforce referential integrity
- Tests pass
```

**Label:** `database`
**Status:** Done

---

## Ticket 11: Add Event Sourcing Event Store (DEMO TICKET)

**Summary:** `Implement event store table for event sourcing architecture`

**Description:**
```
Design and implement foundational event store table to support event sourcing patterns across the platform.

REQUIREMENTS
- Create events table to store domain events for audit trail and event replay
- Each event stores: id, aggregate_type, aggregate_id, event_type, payload (JSON), version, timestamp
- Support event ordering by aggregate and global ordering
- Enable efficient queries for event streams by aggregate

CONSTRAINTS
- Must maintain causality ordering
- Should support efficient replay of events for state reconstruction
- Consider storage volume — events accumulate indefinitely
- Ensure strong consistency for concurrent event appends to same aggregate

ACCEPTANCE CRITERIA
- Events table created with proper indexes
- Event stream queries return events in causal order
- Concurrent appends to same aggregate are serialized
- Migration is reversible
- 10,000 event inserts complete in < 5s
```

**Label:** `database`
**Status:** Backlog (will be created by LeadSync during demo)

---

## How to Use This Scenario

### Step 1: Create Tickets 1-10 in Jira

Use this sequence:
1. In Jira, create a new project or use existing one
2. Create 10 tickets with the above titles, descriptions, and label `database`
3. Mark **Tickets 1-10 as `Done`** (transition to Done status)
4. Keep **Ticket 11 in Backlog** (or create it manually, don't set to Done yet)

### Step 2: Run Demo with Ticket 11

When you create **Ticket 11** in Jira (or simulate the webhook):

**Expected LeadSync Behavior:**
1. Webhook fires for Ticket 11
2. LeadSync identifies label: `database`
3. Loads `templates/db-ruleset.md` (schema minimalism rules, migration safety, etc.)
4. Loads tech lead preferences from Google Docs `LEADSYNC_DATABASE_PREFS_DOC_ID`
5. **Runs same-label history query** → retrieves Tickets 1-10 (last 10 completed `database` tickets)
6. **Generates enriched description** with progression notes:
   - Ticket 1 was foundational schema
   - Tickets 2-4 extended with security/audit layers
   - Tickets 5-6 added multi-tenant support
   - Tickets 7-9 added auth/session/device tracking
   - Ticket 10 added OAuth integration
   - **Ticket 11 is now event sourcing** → complementary to existing auth/session patterns
7. **Generates prompt** with:
   - Task (event sourcing architecture)
   - Context (progression from identity → security → multi-tenancy → auth sessions → OAuth → now events)
   - Constraints (causality ordering, replay capability, storage volume)
   - Implementation Rules (from db-ruleset + tech lead prefs)
   - Key Files (identifies related schema files)
   - Expected Output (migration + tests)

### Step 3: Verify Slack Q&A Integration

After Ticket 11 is created, ask in Slack:
```
/leadsync LEADS-11 Should I add an events_processing table or reuse the events table?
```

**Expected Response:**
- Retrieves Ticket 11 context
- Sees previous tickets 1-10
- Applies database preferences (table minimalism, new entity rules)
- Responds with opinionated answer:
  - "Events table stores immutable events. Processing state (which events have been processed, by which service) is a new concern with its own lifecycle → new table."
  - "Create events_processing table with (id, event_id, processor_name, processed_at, status)."

---

## Notes for Demo Facilitator

- **Progression narrative:** Each ticket builds on previous knowledge, showing how LeadSync understands development evolution
- **Category consistency:** All 10 tickets are `database` label — demonstrates same-label history retrieval
- **Ruleset & preferences application:** Database rules (schema minimalism, migration safety) should appear in generated prompt
- **Precedent context:** The `### Previous Progress (Same Label)` section should list all 10 tickets, organized by theme
- **Slack integration:** Q&A command uses the same historical context to give informed recommendations

---

## Variations for Extended Demo

### Backend Category (Optional)
Create a similar progression for `backend` tickets:
1. API endpoints setup
2. Request validation
3. Error handling
4. Rate limiting
5. Authentication middleware
6. Authorization checks
7. Logging & observability
8. Caching layer
9. Async job processing
10. Circuit breaker patterns

### Frontend Category (Optional)
Create a similar progression for `frontend` tickets:
1. Component library setup
2. State management
3. Routing
4. Form handling
5. Authentication UI
6. Accessibility enhancements
7. Error boundaries
8. Performance optimization
9. Internationalization (i18n)
10. Dark mode support

---

## Success Criteria

✅ **Ticket 11 is created** → LeadSync enriches it automatically
✅ **Prompt is generated** with progression context from Tickets 1-10
✅ **Same-label history appears** in Jira comment showing development trajectory
✅ **Slack Q&A** correctly applies team preferences from Ticket 11's context
✅ **Rules are applied** (db-ruleset visible in prompt)
✅ **Key files** identified from GitHub (if repo is integrated)
✅ **Logs show** context gathering, preference loading, history retrieval
