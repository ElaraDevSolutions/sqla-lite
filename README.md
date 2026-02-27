# sqla-lite

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0%2B-red.svg)](https://www.sqlalchemy.org/)

**sqla-lite** is a lightweight, declarative, and elegant wrapper over **SQLAlchemy**. It is designed to bring the joy and simplicity of frameworks like **Java Spring Boot / JPA** to Python, enabling you to define entities and repositories without the boilerplate of manually mapping declarative bases and session handlers.

Tired of using `Mapped[int] = mapped_column(...)` over and over? Welcome to **sqla-lite**.

---

## 📦 Installation

This library relies strictly on **SQLAlchemy >= 2.0.0** features. Ensure you have the dependencies installed:

```bash
pip install -r requirements.txt
# OR
pip install sqlalchemy>=2.0.0
```

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

---

## ⚡ Intermediate Usage

### Type Inferences and Specific Mappings

`sqla-lite` understands your annotations and makes reasonable defaults.
* `str` automatically becomes `String(256)` if no `Size()` is provided.
* `float` becomes `Float`.
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
