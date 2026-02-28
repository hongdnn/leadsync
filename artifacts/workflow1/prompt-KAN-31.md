```markdown
## Task
Implement user API management features, including advance list querying, profile updates, and summary statistics.

## Context
This task, KAN-31, focuses on enhancing user API management by adding capabilities for advanced list querying, user profile updates, and the generation of summary statistics for user data. No prior work under the 'backend' label has been completed or is available for summary to inform this development phase.

## Key Files
- `demo/api/user_routes.py` - Implements user-related API endpoints for management, profile updates, and potentially list querying. (confidence: high)
- `demo/services/user_service.py` - Contains business logic for user management, profile updates, and potentially advanced data retrieval for lists and stats. (confidence: high)
- `demo/models/user.py` - Defines the data structure for user profiles and related attributes, essential for profile updates. (confidence: medium)
- `demo/utils/query_builder.py` - Provides helper functions for constructing advanced list queries based on various criteria. (confidence: medium)
- `demo/analytics/stats_calculator.py` - Handles logic for aggregating and calculating summary statistics for user data. (confidence: low)
- `demo/tests/api/test_user_routes.py` - Unit and integration tests for user API management features. (confidence: medium)
- `demo/schemas/user_schema.py` - Defines request and response schemas for user data, crucial for API management. (confidence: medium)
## Constraints
- The issue description is high-level, requiring assumptions about specific implementation details.
- No direct tool available to search for commits within a specific timeframe that are directly related to the issue's scope.
- No direct tool available to search for specific file patterns or content within the `demo/` directory, requiring educated guesses based on common project structures and the issue description.

## Implementation Rules
- Keep endpoints idempotent when possible.
- Validate inputs and return explicit error messages.
- Include tests for success and failure paths.

## Expected Output
- Implemented API endpoints for user profile updates, advanced list querying, and summary statistics generation.
- Corresponding service layer logic for user management and data processing.
- Updated or new data models/schemas as required.
- Comprehensive unit and integration tests covering success and failure paths for all new features.
- Any necessary updates to API documentation (e.g., OpenAPI spec).
```
