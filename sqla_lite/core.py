from typing import Any, Type, Optional, List, Union, get_origin, get_args, ForwardRef
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, TypeDecorator, DateTime, Date, ForeignKey, ForeignKeyConstraint, UniqueConstraint, Table, Column
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

class ManyToOne:
    """Marker for many-to-one relationships with support for simple/composite foreign keys."""
    def __init__(self, fields: Union[str, List[str]], nullable: bool = True, back_populates: Optional[str] = None):
        self.fields = fields
        self.nullable = nullable
        self.back_populates = back_populates

class OneToOne:
    """Marker for one-to-one relationships with support for simple/composite foreign keys."""
    def __init__(self, fields: Union[str, List[str]], nullable: bool = True, back_populates: Optional[str] = None):
        self.fields = fields
        self.nullable = nullable
        self.back_populates = back_populates

class OneToMany:
    """Marker for one-to-many relationships. Use list annotation in the attribute type."""
    def __init__(self, mapped_by: Optional[str] = None):
        self.mapped_by = mapped_by

class ManyToMany:
    """Marker for many-to-many relationships. Use list annotation in the attribute type."""
    def __init__(self, mapped_by: Optional[str] = None, table_name: Optional[str] = None):
        self.mapped_by = mapped_by
        self.table_name = table_name


_association_tables: dict[str, Table] = {}


def _normalize_fields(fields: Union[str, List[str]]) -> list[str]:
    if isinstance(fields, str):
        parsed = [item.strip() for item in fields.split(",") if item.strip()]
    else:
        parsed = [str(item).strip() for item in fields if str(item).strip()]
    if not parsed:
        raise ValueError("Relationship fields cannot be empty.")
    return parsed


def _resolve_target_from_annotation(attr_type: Any):
    origin = get_origin(attr_type)
    if origin in (list,):
        args = get_args(attr_type)
        return args[0] if args else None
    return attr_type


def _resolve_target_name(target: Any) -> Optional[str]:
    if isinstance(target, ForwardRef):
        return target.__forward_arg__
    if isinstance(target, str):
        return target
    return None


def _build_secondary_table(left_cls: Type, right_cls: Type, custom_name: Optional[str] = None) -> Table:
    if not hasattr(left_cls, "__table__") or not hasattr(right_cls, "__table__"):
        raise ValueError("ManyToMany requires both sides to be mapped classes.")

    left_table = left_cls.__table__
    right_table = right_cls.__table__

    table_name = custom_name
    if not table_name:
        names = sorted([left_table.name, right_table.name])
        table_name = f"{names[0]}_{names[1]}"

    if table_name in _association_tables:
        return _association_tables[table_name]

    columns = []
    for pk_col in left_table.primary_key.columns:
        columns.append(
            Column(
                f"{left_table.name}_{pk_col.name}",
                pk_col.type,
                ForeignKey(f"{left_table.name}.{pk_col.name}"),
                primary_key=True,
            )
        )

    for pk_col in right_table.primary_key.columns:
        columns.append(
            Column(
                f"{right_table.name}_{pk_col.name}",
                pk_col.type,
                ForeignKey(f"{right_table.name}.{pk_col.name}"),
                primary_key=True,
            )
        )

    association = Table(table_name, Base.metadata, *columns)
    _association_tables[table_name] = association
    return association

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
        table_constraints = []
        relationship_specs = []
        
        # Gets type annotations (e.g., id: int, name: str)
        annotations = getattr(cls, '__annotations__', {})
        
        for attr_name, attr_type in annotations.items():
            # Checks the value assigned to the property
            attr_val = getattr(cls, attr_name, None)

            if isinstance(attr_val, (ManyToOne, OneToOne, OneToMany, ManyToMany)):
                target = _resolve_target_from_annotation(attr_type)

                if isinstance(attr_val, (ManyToOne, OneToOne)):
                    target_name = _resolve_target_name(target)
                    if target_name:
                        raise ValueError(
                            f"{attr_name}: ManyToOne/OneToOne requires a class type annotation, not forward reference."
                        )
                    if target is None:
                        raise ValueError(f"{attr_name}: relationship target could not be resolved.")

                    target_table = getattr(target, "__table__", None)
                    if target_table is None:
                        raise ValueError(f"{attr_name}: target entity must be decorated with @table before use.")

                    fields = _normalize_fields(attr_val.fields)
                    local_cols = []
                    remote_cols = []
                    for field_name in fields:
                        if field_name not in target_table.c:
                            raise ValueError(
                                f"{attr_name}: target field '{field_name}' does not exist in '{target.__name__}'."
                            )
                        remote_cols.append(field_name)
                        local_col_name = f"{attr_name}_{field_name}"
                        local_cols.append(local_col_name)

                        remote_col = target_table.c[field_name]
                        attrs[local_col_name] = mapped_column(remote_col.type, nullable=attr_val.nullable)

                    table_constraints.append(
                        ForeignKeyConstraint(
                            local_cols,
                            [f"{target_table.name}.{col_name}" for col_name in remote_cols],
                        )
                    )

                    if isinstance(attr_val, OneToOne):
                        table_constraints.append(UniqueConstraint(*local_cols))

                    relationship_specs.append(
                        {
                            "kind": "one_to_one" if isinstance(attr_val, OneToOne) else "many_to_one",
                            "attr_name": attr_name,
                            "target": target,
                            "local_cols": local_cols,
                            "back_populates": attr_val.back_populates,
                        }
                    )

                elif isinstance(attr_val, OneToMany):
                    relationship_specs.append(
                        {
                            "kind": "one_to_many",
                            "attr_name": attr_name,
                            "target": target,
                            "target_name": _resolve_target_name(target),
                            "mapped_by": attr_val.mapped_by,
                        }
                    )

                elif isinstance(attr_val, ManyToMany):
                    relationship_specs.append(
                        {
                            "kind": "many_to_many",
                            "attr_name": attr_name,
                            "target": target,
                            "target_name": _resolve_target_name(target),
                            "mapped_by": attr_val.mapped_by,
                            "table_name": attr_val.table_name,
                        }
                    )

                continue
            
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

        if table_constraints:
            attrs["__table_args__"] = tuple(table_constraints)
        
        # Creates a new class derived from SQLAlchemy DeclarativeBase
        sqla_class = type(cls.__name__, (Base,), attrs)

        for spec in relationship_specs:
            kind = spec["kind"]

            if kind in ("many_to_one", "one_to_one"):
                relation_kwargs = {
                    "foreign_keys": [getattr(sqla_class, col_name) for col_name in spec["local_cols"]]
                }
                if spec["back_populates"]:
                    relation_kwargs["back_populates"] = spec["back_populates"]
                if kind == "one_to_one":
                    relation_kwargs["uselist"] = False
                setattr(sqla_class, spec["attr_name"], relationship(spec["target"], **relation_kwargs))

            elif kind == "one_to_many":
                target = spec["target_name"] if isinstance(spec["target"], ForwardRef) else (spec["target"] or spec["target_name"])
                relation_kwargs = {}
                if spec["mapped_by"]:
                    relation_kwargs["back_populates"] = spec["mapped_by"]
                setattr(sqla_class, spec["attr_name"], relationship(target, **relation_kwargs))

            elif kind == "many_to_many":
                target = spec["target"]
                if target is None or isinstance(target, (ForwardRef, str)) or not hasattr(target, "__table__"):
                    raise ValueError(
                        f"{spec['attr_name']}: ManyToMany requires a concrete target class annotation (e.g., list[Role])."
                    )
                secondary = _build_secondary_table(sqla_class, target, spec["table_name"])
                relation_kwargs = {"secondary": secondary}
                if spec["mapped_by"]:
                    relation_kwargs["back_populates"] = spec["mapped_by"]
                setattr(sqla_class, spec["attr_name"], relationship(target, **relation_kwargs))

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
