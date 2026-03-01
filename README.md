# sqla-lite

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0%2B-red.svg)](https://www.sqlalchemy.org/)

**sqla-lite** is a lightweight, declarative, and elegant wrapper over **SQLAlchemy**. It is designed to bring the joy and simplicity of frameworks like **Java Spring Boot / JPA** to Python, enabling you to define entities and repositories without the boilerplate of manually mapping declarative bases and session handlers.

Tired of using `Mapped[int] = mapped_column(...)` over and over? Welcome to **sqla-lite**.

Want to contribute? See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## 📦 Installation

Install directly from **PyPI**:

```bash
pip install sqla-lite
```

`sqla-lite` already brings its runtime dependency (`SQLAlchemy >= 2.0.0`).

---

## 🚀 Quick Start (The Basics)

Define your models exactly like you would writing pure Python data structures. Use the `@table` class decorator instead of dealing with explicit inheritance from `DeclarativeBase`. 

You can annotate your attributes by assigning the markers (`Id()`, `Size()`) directly!

```python
from sqla_lite import table, Id, Size

@table("users")
class User:
    id: int = Id()             # Automatically setup as Primary Key
    name: str = Size(100)      # VARCHAR(100)
    age: int                   # Automatically inferred as Integer
```

### Automatic Repositories

Say goodbye to the `with Session(engine) as session:` nightmare. With **sqla-lite**, you can register a repository to manage your Data Access layer globally for an entity!

```python
from sqla_lite import repository, configure_database

# 1. Define an empty Repository pointing to your Entity
@repository(User)
class UserRepository:
    pass

# 2. Configure your Database globally ONCE (Usually at the start of your application)
from sqlalchemy import create_engine
engine = create_engine("sqlite:///:memory:")

# sqla-lite will generate all tables automatically in Base.metadata (if needed)
from sqla_lite.core import Base
Base.metadata.create_all(engine)

# Inform sqla-lite to use this global engine!
configure_database(engine)

# 3. Use it! No sessions needed!
repo = UserRepository()

user = User(name="John Doe", age=25)
repo.save(user) # Auto-commits

# Search by primary key natively!
john = repo.get(1)
print(john.name)
```

### Simplified Query Methods (`@query`)

For simple filters, you can avoid manual session boilerplate by using `@query`.
The decorated method receives a query context already bound to `self.entity_class`.

```python
from sqla_lite import repository, query

@repository(User)
class UserRepository:
    @query
    def find_adults(self, session):
        return session.filter(self.entity_class.age >= 18).all()
```

If you need full control, you can still use `with Session(self.engine) as session:` normally.

---

## ⚡ Intermediate Usage

### Type Inferences and Specific Mappings

`sqla-lite` understands your annotations and makes reasonable defaults.
* `str` automatically becomes `String(256)` if no `Size()` is provided.
* `float` becomes `Float`.
* `id: str = Id()` automatically generates a UUID when no value is informed.
* Want highly-precise decimal numbers for currencies? Use the `Decimal` marker!

```python
from sqla_lite import Decimal

@table("products")
class Product:
    id: int = Id()
    title: str = Size(150)
    
    # 10 digits in total, 2 fractional decimal numbers -> Numeric(10, 2)
    price: float = Decimal(precision=10, scale=2) 
```

```python
@table("uuid_products")
class UuidProduct:
    id: str = Id()  # Auto-generated UUID if omitted
    title: str = Size(150)
```


### Date Handling

Handling Date strings and casting them into Database `Datetime` correctly can be a headache. `sqla-lite` supports both:
1. **Native Python formats**: Using `datetime.datetime` directly.
2. **String Parsing Formats**: Use the `DateFormat` to transparently map python Strings into database `DateTime` seamlessly!

```python
import datetime
from sqla_lite import DateFormat

@table("events")
class Event:
    id: int = Id()
    
    # Kept as native Datetime everywhere
    created_at: datetime.datetime 
    
    # Allows assigning strings in Python ("27/02/2026"). It'll be saved as a Datetime on DB!
    completed_at: str = DateFormat("%d/%m/%Y")
```
Example:
```python
evt = Event(
    created_at=datetime.datetime.now(),
    completed_at="27/02/2026"
)
repo.save(evt)
```

---

## 🌋 Advanced Usage

### Composite Primary Keys

If your database design demands more complex structures like Many-To-Many resolution tables, or Legacy composite-keys, simply annotate multiple attributes with the `Id()` marker.

If one of the primary keys is a String and requires a size, you can pass the argument `size=` into the `Id` marker.

```python
@table("employee_roles")
class EmployeeRole:
    # Key 1
    employee_id: int = Id()
    # Key 2: String with length!
    role_name: str = Id(size=50) 
    
    assigned_date: datetime.datetime
```

#### Querying with Repositories over Composite Keys

You don't need tuples or weird abstractions to retrieve composed key rows via our **Repository Pattern**. Just pass your identifiers in the sequence they were declared!

```python
@repository(EmployeeRole)
class EmployeeRoleRepo: pass

repo = EmployeeRoleRepo()

# The Repository handles the argument unpacking dynamically
role = repo.get(101, "Software Engineer")
print(f"Loaded Role for Employee {role.employee_id}!")
```

### Relationships (Foreign Keys)

`sqla-lite` now supports relationship markers for all common cases:

- `ManyToOne` (many rows reference one parent)
- `OneToOne` (unique reference)
- `OneToMany` (list side of one-to-many)
- `ManyToMany` (list-to-list through association table)

#### ManyToOne with simple FK

```python
from sqla_lite import table, Id, Size, Decimal, ManyToOne

@table("products")
class Product:
    id: int = Id()
    title: str = Size(150)
    price: float = Decimal(precision=10, scale=2)

@table("stocks")
class Stock:
    id: int = Id()
    product: Product = ManyToOne(fields="id")
```

This creates `stock.product_id` as foreign key to `products.id`.

#### ManyToOne with composite FK

Use `fields` as comma-separated string or list:

```python
from sqla_lite import table, Id, Size, ManyToOne

@table("companies")
class Company:
    tenant_id: int = Id()
    code: str = Id(size=20)
    name: str = Size(100)

@table("employees")
class Employee:
    id: int = Id()
    company: Company = ManyToOne(fields=["tenant_id", "code"])
```

Equivalent form:

```python
company: Company = ManyToOne(fields="tenant_id,code")
```

#### OneToOne

```python
from sqla_lite import table, Id, Size, OneToOne

@table("profiles")
class Profile:
    id: int = Id()
    user_name: str = Size(80)

@table("profile_details")
class ProfileDetail:
    id: int = Id()
    profile: Profile = OneToOne(fields="id")
```

`OneToOne` applies a unique constraint on the generated FK columns.

#### OneToMany

```python
from sqla_lite import table, Id, Size, ManyToOne, OneToMany

@table("parents")
class Parent:
    id: int = Id()
    name: str = Size(80)
    children: list["Child"] = OneToMany(mapped_by="parent")

@table("children")
class Child:
    id: int = Id()
    parent: Parent = ManyToOne(fields="id", back_populates="children")
    title: str = Size(120)
```

#### ManyToMany

```python
from sqla_lite import table, Id, Size, ManyToMany

@table("permissions")
class Permission:
    id: int = Id()
    name: str = Size(60)

@table("users")
class User:
    id: int = Id()
    user_name: str = Size(80)
    permissions: list[Permission] = ManyToMany()
```

An association table is generated automatically.

---

## 🔥 Extending Repositories

Because your Repository is a plain Python Class wrapped by `@repository`, you can implement custom behavior that fits your business logic inside of it. The decorator only injects basic (`save`, `get`, `delete`, `find_all`) methods, leaving you free to query anything else you like via `self.engine`:

```python
from sqlalchemy.orm import Session

@repository(User)
class UserRepository:
    def find_adults(self):
        with Session(self.engine) as session:
            # self.entity_class holds a reference to the mapped Class!
            return session.query(self.entity_class).filter(self.entity_class.age >= 18).all()

# Usage:
repo = UserRepository()
adults = repo.find_adults()
```

---
*Created with ❤️. Say goodbye to boilerplate code!*

Support this project on Patreon: https://www.patreon.com/cw/ElaraDevSolutions
