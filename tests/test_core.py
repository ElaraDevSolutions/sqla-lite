import pytest
from sqlalchemy import create_engine
import datetime
from sqla_lite import table, Id, Size, Decimal, DateFormat, ManyToOne, OneToMany, ManyToMany, OneToOne, repository, configure_database
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

@table("mock_companies")
class MockCompany:
    tenant_id: int = Id()
    code: str = Id(size=20)
    display_name: str = Size(100)

@table("mock_employees")
class MockEmployee:
    id: int = Id()
    company: MockCompany = ManyToOne(fields=["tenant_id", "code"])
    full_name: str = Size(100)

@table("mock_profiles")
class MockProfile:
    id: int = Id()
    user_name: str = Size(80)

@table("mock_profile_details")
class MockProfileDetail:
    id: int = Id()
    profile: MockProfile = OneToOne(fields="id")
    bio: str = Size(120)

@table("mock_rel_parents")
class MockRelParent:
    id: int = Id()
    name: str = Size(80)
    children: list["MockRelChild"] = OneToMany(mapped_by="parent")

@table("mock_rel_children")
class MockRelChild:
    id: int = Id()
    parent: MockRelParent = ManyToOne(fields="id", back_populates="children")
    title: str = Size(120)

@table("mock_permissions")
class MockPermission:
    id: int = Id()
    name: str = Size(60)

@table("mock_security_users")
class MockSecUser:
    id: int = Id()
    user_name: str = Size(80)
    permissions: list[MockPermission] = ManyToMany()

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


def test_many_to_one_composite_fk_mapping(setup_database):
    mapper = MockEmployee.__mapper__
    columns = mapper.columns

    assert "company_tenant_id" in columns
    assert "company_code" in columns

    fk_columns = sorted([col.parent.name for fk in mapper.local_table.foreign_key_constraints for col in fk.elements])
    assert fk_columns == ["company_code", "company_tenant_id"]


def test_one_to_one_mapping_creates_unique_constraint(setup_database):
    table = MockProfileDetail.__mapper__.local_table
    unique_sets = [set(constraint.columns.keys()) for constraint in table.constraints if constraint.__class__.__name__ == "UniqueConstraint"]
    assert {"profile_id"} in unique_sets


def test_one_to_many_relationship_is_list(setup_database):
    relation = MockRelParent.__mapper__.relationships["children"]
    assert relation.uselist is True


def test_many_to_many_relationship_uses_secondary_table(setup_database):
    relation = MockSecUser.__mapper__.relationships["permissions"]
    assert relation.secondary is not None


def test_many_to_one_accepts_comma_separated_composite_fields(setup_database):
    @table("mock_employees_csv_fk")
    class MockEmployeeCsvFk:
        id: int = Id()
        company: MockCompany = ManyToOne(fields="tenant_id,code")
        full_name: str = Size(100)

    mapper = MockEmployeeCsvFk.__mapper__
    columns = mapper.columns

    assert "company_tenant_id" in columns
    assert "company_code" in columns


def test_many_to_one_nullable_false_marks_generated_fk_columns_not_null(setup_database):
    @table("mock_non_nullable_employee")
    class MockNonNullableEmployee:
        id: int = Id()
        company: MockCompany = ManyToOne(fields=["tenant_id", "code"], nullable=False)

    mapper = MockNonNullableEmployee.__mapper__
    assert mapper.columns["company_tenant_id"].nullable is False
    assert mapper.columns["company_code"].nullable is False


def test_back_populates_is_wired_for_many_to_one_and_one_to_many(setup_database):
    parent_rel = MockRelParent.__mapper__.relationships["children"]
    child_rel = MockRelChild.__mapper__.relationships["parent"]

    assert parent_rel.back_populates == "parent"
    assert child_rel.back_populates == "children"


def test_one_to_one_relationship_is_scalar(setup_database):
    relation = MockProfileDetail.__mapper__.relationships["profile"]
    assert relation.uselist is False


def test_many_to_one_raises_for_invalid_target_field_name():
    with pytest.raises(ValueError, match="target field 'missing_field' does not exist"):
        @table("mock_invalid_field_fk")
        class _InvalidFieldFk:
            id: int = Id()
            company: MockCompany = ManyToOne(fields="missing_field")


def test_many_to_one_raises_for_empty_fields_definition():
    with pytest.raises(ValueError, match="Relationship fields cannot be empty"):
        @table("mock_empty_fields_fk")
        class _EmptyFieldsFk:
            id: int = Id()
            company: MockCompany = ManyToOne(fields="  ,   ")


def test_many_to_many_raises_for_missing_target_type_annotation():
    with pytest.raises(ValueError, match="ManyToMany requires a concrete target class annotation"):
        @table("mock_invalid_many_to_many")
        class _InvalidManyToMany:
            id: int = Id()
            permissions: list = ManyToMany()


def test_one_to_one_composite_creates_unique_constraint_for_all_fk_columns(setup_database):
    @table("mock_external_accounts")
    class MockExternalAccount:
        tenant_id: int = Id()
        external_id: str = Id(size=50)

    @table("mock_external_account_profiles")
    class MockExternalAccountProfile:
        id: int = Id()
        account: MockExternalAccount = OneToOne(fields=["tenant_id", "external_id"])

    table_obj = MockExternalAccountProfile.__mapper__.local_table
    unique_sets = [set(constraint.columns.keys()) for constraint in table_obj.constraints if constraint.__class__.__name__ == "UniqueConstraint"]
    assert {"account_tenant_id", "account_external_id"} in unique_sets
