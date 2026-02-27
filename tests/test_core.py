import pytest
from sqlalchemy import create_engine
import datetime
from sqla_lite import table, Id, Size, Decimal, DateFormat, repository, configure_database
from sqla_lite.core import Base

# --- ENTITIES FOR TESTING ---

@table("mock_users")
class MockUser:
    id: int = Id()
    name: str = Size(50)
    age: int

@table("mock_products")
class MockProduct:
    # Testing implicit string length logic and implicit float mapping 
    code: str = Id()
    price: float = Decimal(precision=10, scale=2)

@table("mock_events")
class MockEvent:
    id: int = Id()
    created_at: datetime.datetime
    scheduled_date: str = DateFormat("%Y-%m-%d")

@table("mock_composite_roles")
class MockCompositeRole:
    org_id: int = Id()
    role_name: str = Id(size=20)
    clearance: int

# --- REPOSITORIES FOR TESTING ---

@repository(MockUser)
class MockUserRepository:
    pass

@repository(MockProduct)
class MockProductRepository:
    pass

@repository(MockEvent)
class MockEventRepository:
    pass

@repository(MockCompositeRole)
class MockCompositeRoleRepository:
    # Custom method to test repository extensibility
    def change_clearance(self, org, role, val):
        entity = self.get(org, role)
        entity.clearance = val
        self.save(entity)


# --- FIXTURES ---

@pytest.fixture(scope="function")
def setup_database():
    """Sets up an in-memory SQLite database before each test, and clears it."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    configure_database(engine)
    yield engine
    # Teardown logic
    Base.metadata.drop_all(engine)


# --- UNIT TESTS ---

def test_type_inferences_and_mapping(setup_database):
    """Verifies that the @table decorator sets up native SQLAlchemy mapping correctly."""
    mapper = MockUser.__mapper__
    assert mapper.local_table.name == "mock_users"
    
    # Check Columns mappings
    columns = mapper.columns
    assert "id" in columns
    assert columns["id"].primary_key is True
    
    assert "name" in columns
    assert str(columns["name"].type) == "VARCHAR(50)"
    
    assert "age" in columns
    assert str(columns["age"].type) == "INTEGER"


def test_basic_repository_save_and_get(setup_database):
    """Tests basic CRUD saving and querying capabilities."""
    repo = MockUserRepository()
    
    # Save test
    new_user = MockUser(name="Alice", age=28)
    repo.save(new_user)
    
    # Needs to have auto-incremented an ID locally
    assert new_user.id is not None
    
    # Get test
    fetched_user = repo.get(new_user.id)
    assert fetched_user is not None
    assert fetched_user.name == "Alice"
    assert fetched_user.age == 28


def test_repository_find_all_and_delete(setup_database):
    """Tests returning lists and removing records."""
    repo = MockUserRepository()
    repo.save(MockUser(name="Bob", age=30))
    repo.save(MockUser(name="Charlie", age=35))
    
    users = repo.find_all()
    assert len(users) == 2
    
    charlie = repo.get(2)
    repo.delete(charlie)
    
    remaining = repo.find_all()
    assert len(remaining) == 1
    assert remaining[0].name == "Bob"


def test_decimal_and_string_pk(setup_database):
    """Tests @Decimal usage and String as Primary Keys without auto-increase."""
    repo = MockProductRepository()
    
    p = MockProduct(code="PROD-AX", price=199.99)
    repo.save(p)
    
    fetched = repo.get("PROD-AX")
    assert fetched.code == "PROD-AX"
    
    assert type(fetched.price) != float # SQLAlchemy numeric mapped type verification (usually Decimal here)
    assert float(fetched.price) == 199.99


def test_date_conversion_formats(setup_database):
    """Tests Date conversions between str/datetime and @DateFormat wrapper."""
    repo = MockEventRepository()
    
    start_time = datetime.datetime(2026, 2, 27, 10, 0)
    
    evt = MockEvent(
        created_at=start_time,
        scheduled_date="2026-12-25"
    )
    repo.save(evt)
    
    fetched = repo.get(1)
    
    # Native datetime should be intact
    assert isinstance(fetched.created_at, datetime.datetime)
    
    # Custom format marker should read from Sqlite string perfectly parsed into our layout
    assert isinstance(fetched.scheduled_date, str)
    assert fetched.scheduled_date == "2026-12-25"


def test_repository_composite_keys(setup_database):
    """Tests handling tuples properly inside repository's dynamically mapped .get() arguments."""
    repo = MockCompositeRoleRepository()
    
    # Add
    repo.save(MockCompositeRole(org_id=10, role_name="Admin", clearance=5))
    
    # Fetch unmapped flat args (10, Admin)
    role = repo.get(10, "Admin")
    assert role is not None
    assert role.clearance == 5
    
    # Call a custom extended Repo feature!
    repo.change_clearance(10, "Admin", 99)
    
    updated_role = repo.get(10, "Admin")
    assert updated_role.clearance == 99
