# Quick Start: Running Client View Tests

## File Locations

```
/backend/apps/users/tests/test_client_views.py          (57 tests)
/backend/apps/transactions/tests/test_client_views.py   (47 tests)
/backend/apps/properties/tests/test_client_views.py     (37 tests)
/backend/apps/appointments/tests/test_client_views.py   (39 tests)
```

Total: **180+ test methods** across **4 files**

---

## Running Tests

### Run All Client Tests
```bash
python manage.py test \
  apps.users.tests.test_client_views \
  apps.transactions.tests.test_client_views \
  apps.properties.tests.test_client_views \
  apps.appointments.tests.test_client_views
```

### Run by App
```bash
# Users client views
python manage.py test apps.users.tests.test_client_views

# Transactions client views
python manage.py test apps.transactions.tests.test_client_views

# Properties client views
python manage.py test apps.properties.tests.test_client_views

# Appointments client views
python manage.py test apps.appointments.tests.test_client_views
```

### Run Specific Test Class
```bash
# Run all dashboard tests
python manage.py test apps.users.tests.test_client_views.TestClientDashboard

# Run all profile tests
python manage.py test apps.users.tests.test_client_views.TestClientProfile

# Run all purchase document upload tests
python manage.py test apps.transactions.tests.test_client_views.TestClientPurchaseDocumentUpload
```

### Run Specific Test Method
```bash
# Run single test
python manage.py test apps.users.tests.test_client_views.TestClientProfile.test_get_profile_returns_200

# Run with verbose output
python manage.py test apps.users.tests.test_client_views.TestClientProfile.test_get_profile_returns_200 -v 2
```

---

## Coverage Analysis

### Generate Coverage Report
```bash
# Run with coverage
coverage run --source='apps' manage.py test \
  apps.users.tests.test_client_views \
  apps.transactions.tests.test_client_views \
  apps.properties.tests.test_client_views \
  apps.appointments.tests.test_client_views

# Generate report
coverage report

# Generate HTML report
coverage html
open htmlcov/index.html
```

### Expected Coverage
- **apps/users/views/client.py**: 95%+
- **apps/transactions/views/client.py**: 95%+
- **apps/properties/views/client.py**: 95%+
- **apps/appointments/views/client.py**: 95%+

---

## Test Structure

Each test file follows this pattern:

```
test_client_views.py
├── Helper Functions
│   ├── _token(user)          # Generate JWT token
│   ├── _auth(token)          # Create auth header
│   └── _fake_*()             # Create test fixtures (PDF, image, etc.)
├── Setup Class
│   └── *Setup(APITestCase)   # Create tenant, users, memberships, etc.
└── Test Classes
    ├── Test*List             # GET list endpoints (pagination, filtering)
    ├── Test*Detail           # GET detail endpoints (404, isolation)
    ├── Test*Create/Update    # POST/PATCH/PUT endpoints
    ├── Test*Delete           # DELETE endpoints (404, idempotent)
    └── Test*Validation       # Field validation, error conditions
```

---

## What's Tested

### Authentication & Authorization ✅
- 401 Unauthorized (no token)
- 403 Forbidden (insufficient permissions)
- 200 OK (valid token)
- Token expiration (if needed)

### Multi-Tenant Safety ✅
- Client can only access own data
- Viewing other client's data returns 404
- Cross-tenant requests rejected
- Tenant isolation enforced

### CRUD Operations ✅
- CREATE (POST) - new resource creation
- READ (GET) - list and detail
- UPDATE (PATCH/PUT) - field updates
- DELETE - resource removal

### Pagination & Filtering ✅
- Limit/offset pagination
- Ordering (most recent first, etc.)
- Filtering by status, date, etc.

### Validation & Constraints ✅
- Required fields validated
- Data types checked
- Unique constraints enforced
- Business logic constraints

### State Machine Validation ✅
- Appointment cancellation only on valid states
- Document upload only on valid pipeline stages
- Terminal states protected

### File Operations ✅
- Upload with temp directories
- Magic bytes validation
- Filename sanitization
- Metadata tracking

---

## Test Data Setup

Each test creates:
- **Tenant**: Isolated multi-tenant environment
- **Users**: Client, Agent, Admin (as needed)
- **Memberships**: Role-based access control
- **Related Models**: Property, Appointment, etc.
- **Locations**: Country, State, City hierarchy

Example:
```python
def setUp(self):
    self.tenant = Tenant.objects.create(
        name='Test Tenant',
        slug='test-tenant',
        email='test@test.com',
        is_active=True,
    )
    self.user = User.objects.create(
        email='user@test.com',
        is_active=True,
    )
    self.membership = TenantMembership.objects.create(
        user=self.user,
        tenant=self.tenant,
        role=TenantMembership.Role.CLIENT,
        is_active=True,
    )
    self.token = _token(self.user)
```

---

## Interpreting Results

### All Tests Pass ✅
```
Ran 180 tests in 15.234s
OK
```

### Some Tests Fail ❌
```
FAILED: test_name
AssertionError: 404 != 200
```

Check:
1. View implementation matches test expectations
2. URL routing correct
3. Permissions configured
4. Serializers returning correct data

### Coverage Report
```
apps/users/views/client.py        95%  (156 statements, 8 missing)
apps/transactions/views/client.py 96%  (82 statements, 3 missing)
apps/properties/views/client.py    94%  (48 statements, 3 missing)
apps/appointments/views/client.py  97%  (30 statements, 1 missing)
```

Uncovered lines typically are:
- Unreachable error paths
- Conditional imports
- Debug code

---

## Common Issues & Solutions

### ImportError: No module named 'django'
```bash
# Activate virtual environment
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### Database Error: no such table
```bash
# Run migrations
python manage.py migrate
```

### Connection refused: can't connect to localhost:5432
```bash
# Check PostgreSQL is running
brew services start postgresql

# Or use SQLite for tests (default)
```

### Test timeout (taking too long)
```bash
# Run with keepdb to reuse database
python manage.py test --keepdb

# Run in parallel
python manage.py test --parallel 4
```

### Temporary file cleanup issues
```python
# Tests use override_settings with tempfile.mkdtemp()
# Django cleans up automatically after each test
```

---

## Integration with CI/CD

### GitHub Actions Example
```yaml
- name: Run Client View Tests
  run: |
    python manage.py test \
      apps.users.tests.test_client_views \
      apps.transactions.tests.test_client_views \
      apps.properties.tests.test_client_views \
      apps.appointments.tests.test_client_views \
      --no-migrations
```

### GitLab CI Example
```yaml
test:
  script:
    - python manage.py test apps.*.tests.test_client_views
  coverage: '/TOTAL.*\s+(\d+%)$/'
```

---

## Best Practices

1. **Run tests before committing**
   ```bash
   python manage.py test apps.users.tests.test_client_views
   ```

2. **Check coverage regularly**
   ```bash
   coverage report --fail-under=90
   ```

3. **Add new tests when fixing bugs**
   - Write failing test first
   - Fix the bug
   - Verify test passes

4. **Keep tests isolated**
   - Each test should be independent
   - No shared state between tests
   - Use setUp() to initialize data

5. **Use descriptive test names**
   - Clear intent: `test_get_endpoint_returns_200`
   - Include expected behavior
   - Use assertions with messages

---

## Additional Resources

- Django Testing Documentation: https://docs.djangoproject.com/en/stable/topics/testing/
- DRF Testing: https://www.django-rest-framework.org/api-guide/testing/
- Coverage.py: https://coverage.readthedocs.io/
- pytest-django: https://pytest-django.readthedocs.io/

---

## Success Criteria

✅ All tests pass
✅ 95%+ code coverage on each view file
✅ No warnings or deprecations
✅ Tests run in < 30 seconds
✅ Clear, actionable error messages
✅ Isolated and independent tests
✅ Production-ready code

