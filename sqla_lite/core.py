from typing import Any, Type, Optional
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, TypeDecorator, DateTime, Date
import datetime

class Base(DeclarativeBase):
    pass

class Id:
    """Marker for primary key (@Id)"""
    def __init__(self, size: Optional[int] = None):
        self.size = size

class Size:
    """Marker for the maximum column size (Equivalent to @Size)"""
    def __init__(self, size: int = 256):
        self.size = size

class Decimal:
    """Marker for decimal precision and scale (Equivalent to @Decimal)"""
    def __init__(self, precision: int, scale: int):
        self.precision = precision
        self.scale = scale

class DateFormat(TypeDecorator):
    """
    Custom SQLAlchemy Type to handle Date formatting automatically.
    Converts strictly between Python strings/datetimes and Database DateTimes based on a format string.
    """
    impl = DateTime
    # Keeps it as a DateTime column when cached or processed by SQLite/PostgreSQL
    cache_ok = True

    def __init__(self, format: str = "%Y-%m-%d %H:%M:%S", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.format = format

    def process_bind_param(self, value, dialect):
        # Convert String -> Datetime BEFORE saving to DB
        if value is None:
            return None
        if isinstance(value, str):
            try:
                # If we passed a string like "27/02/2026", Python converts it to Datetime object for SQLAlchemy
                return datetime.datetime.strptime(value, self.format)
            except ValueError:
                raise ValueError(f"Date string '{value}' does not match format '{self.format}'")
        return value # Returns native datetime if it's already one

    def process_result_value(self, value, dialect):
        # Convert Datetime -> String AFTER loading from DB
        # The user's Python class instance will see a formatted String if they desire, instead of a raw Datetime.
        if value is not None and isinstance(value, datetime.datetime):
            return value.strftime(self.format)
        return value

class DateFormatMarker:
    """Marker for date format properties (Equivalent to @JsonFormat or @DateTimeFormat)"""
    def __init__(self, format: str = "%Y-%m-%d %H:%M:%S"):
        self.format = format

def table(name: str):
    """
    It intercepts the annotated class and returns a compatible SQLAlchemy class.
    """
    def decorator(cls: Type) -> Type[Base]:
        attrs = {
            '__tablename__': name,
            '__module__': cls.__module__,
            '__doc__': cls.__doc__
        }
        
        # Gets type annotations (e.g., id: int, name: str)
        annotations = getattr(cls, '__annotations__', {})
        
        for attr_name, attr_type in annotations.items():
            # Checks the value assigned to the property
            attr_val = getattr(cls, attr_name, None)
            
            # Map Python native types to SQLAlchemy types
            sa_type = None
            if attr_type == int:
                sa_type = Integer
            elif attr_type == str:
                sa_type = String(256)
            elif attr_type == float:
                from sqlalchemy import Float
                sa_type = Float
            elif attr_type == datetime.datetime:
                sa_type = DateTime
            elif attr_type == datetime.date:
                sa_type = Date

            # Is it a primary key?
            if isinstance(attr_val, Id):
                if attr_type == str and attr_val.size is not None:
                    # If it is a String and has a explicit size set in the Id
                    sa_type = String(attr_val.size)
                attrs[attr_name] = mapped_column(sa_type, primary_key=True)
            
            # Does it have a specific size?
            elif isinstance(attr_val, Size):
                # When using Size, we can also configure if it's part of a composite primary key
                is_pk = getattr(attr_val, 'primary_key', False)
                attrs[attr_name] = mapped_column(String(attr_val.size), primary_key=is_pk)
                
            # Is it a decimal with precision?
            elif isinstance(attr_val, Decimal):
                from sqlalchemy import Numeric
                is_pk = getattr(attr_val, 'primary_key', False)
                attrs[attr_name] = mapped_column(Numeric(attr_val.precision, attr_val.scale), primary_key=is_pk)
                
            # Is it formatted as Date? (Solves Both: string mapped to datetime or datetime mapped to string)
            elif isinstance(attr_val, DateFormatMarker):
                is_pk = getattr(attr_val, 'primary_key', False)
                attrs[attr_name] = mapped_column(DateFormat(format=attr_val.format), primary_key=is_pk)
                
            # Normal attribute (e.g., age: int) without a custom initializer
            else:
                if sa_type:
                    attrs[attr_name] = mapped_column(sa_type)
                else:
                    attrs[attr_name] = mapped_column()
        
        # Creates a new class derived from SQLAlchemy DeclarativeBase
        sqla_class = type(cls.__name__, (Base,), attrs)
        return sqla_class
        
    return decorator


# --- Global Database Configuration for Repositories ---

class DatabaseContext:
    engine = None

def configure_database(engine):
    """Sets the global engine for the sqla-lite framework."""
    DatabaseContext.engine = engine


def repository(entity_class: Type):
    """
    Class decorator equivalent to Spring's @Repository(Entity).
    Injects standard database operations methods transparently.
    """
    def decorator(cls: Type):
        def __init__(self, engine=None):
            self.engine = engine or DatabaseContext.engine
            if not self.engine:
                raise Exception("No database engine configured. Use 'configure_database(engine)' or pass it to the constructor.")
        
        def save(self, entity):
            from sqlalchemy.orm import Session
            with Session(self.engine, expire_on_commit=False) as session:
                session.add(entity)
                session.commit()
                return entity

        def get(self, *ident):
            from sqlalchemy.orm import Session
            with Session(self.engine, expire_on_commit=False) as session:
                # If multiple arguments are provided, pass them as a tuple (for composite keys)
                # If only one argument is provided, pass it directly (for simple keys)
                query_ident = ident[0] if len(ident) == 1 else ident
                return session.get(entity_class, query_ident)
                
        def delete(self, entity):
            from sqlalchemy.orm import Session
            with Session(self.engine, expire_on_commit=False) as session:
                entity = session.merge(entity)
                session.delete(entity)
                session.commit()
                
        def find_all(self):
            from sqlalchemy.orm import Session
            with Session(self.engine, expire_on_commit=False) as session:
                return session.query(entity_class).all()

        # Injects the base methods into the Repository class
        setattr(cls, '__init__', __init__)
        setattr(cls, 'save', save)
        setattr(cls, 'get', get)
        setattr(cls, 'delete', delete)
        setattr(cls, 'find_all', find_all)
        setattr(cls, 'entity_class', entity_class)
        
        return cls
    return decorator
