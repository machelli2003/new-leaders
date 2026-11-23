from __future__ import annotations

import hashlib
import json
import re
import uuid
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime
from functools import wraps
from typing import Any

import asyncpg
from pymongo.errors import DuplicateKeyError as MongoDuplicateKeyError


class DuplicateKeyError(MongoDuplicateKeyError):
    pass


def _translate_unique_violation(method):
    @wraps(method)
    async def wrapped(*args, **kwargs):
        try:
            return await method(*args, **kwargs)
        except asyncpg.UniqueViolationError as exc:
            raise DuplicateKeyError(str(exc)) from exc

    return wrapped


class ReturnDocument:
    BEFORE = False
    AFTER = True


@dataclass
class WriteResult:
    matched_count: int = 0
    modified_count: int = 0
    deleted_count: int = 0


@dataclass
class InsertOneResult:
    inserted_id: str


_DATETIME = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d")


def _encode(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _encode(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_encode(v) for v in value]
    return value


def _decode(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _decode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_decode(v) for v in value]
    if isinstance(value, str) and _DATETIME.match(value):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            pass
    return value


def _path_sql(path: str) -> str:
    parts = path.split(".")
    literal = ", ".join("'" + part.replace("'", "''") + "'" for part in parts)
    return f"data #> ARRAY[{literal}]::text[]"


def _path_text_sql(path: str) -> str:
    parts = path.split(".")
    literal = ", ".join("'" + part.replace("'", "''") + "'" for part in parts)
    return f"data #>> ARRAY[{literal}]::text[]"


def _get_path(doc: dict, path: str) -> Any:
    value: Any = doc
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _set_path(doc: dict, path: str, value: Any) -> None:
    parts = path.split(".")
    target = doc
    for part in parts[:-1]:
        child = target.get(part)
        if not isinstance(child, dict):
            child = {}
            target[part] = child
        target = child
    target[parts[-1]] = value


def _unset_path(doc: dict, path: str) -> None:
    parts = path.split(".")
    target = doc
    for part in parts[:-1]:
        target = target.get(part)
        if not isinstance(target, dict):
            return
    target.pop(parts[-1], None)


def _apply_update(doc: dict, update: dict, inserting: bool = False) -> dict:
    result = deepcopy(doc)
    for operator, changes in update.items():
        if operator == "$set" or (operator == "$setOnInsert" and inserting):
            for path, value in changes.items():
                _set_path(result, path, value)
        elif operator == "$setOnInsert":
            continue
        elif operator == "$unset":
            for path in changes:
                _unset_path(result, path)
        elif operator == "$inc":
            for path, amount in changes.items():
                _set_path(result, path, (_get_path(result, path) or 0) + amount)
        elif operator == "$push":
            for path, value in changes.items():
                values = _get_path(result, path)
                if not isinstance(values, list):
                    values = []
                values = list(values)
                if isinstance(value, dict) and "$each" in value:
                    values.extend(value["$each"])
                else:
                    values.append(value)
                _set_path(result, path, values)
        elif operator == "$addToSet":
            for path, value in changes.items():
                values = _get_path(result, path)
                if not isinstance(values, list):
                    values = []
                values = list(values)
                candidates = value.get("$each", []) if isinstance(value, dict) and "$each" in value else [value]
                for candidate in candidates:
                    if candidate not in values:
                        values.append(candidate)
                _set_path(result, path, values)
        elif operator == "$pull":
            for path, condition in changes.items():
                values = _get_path(result, path)
                if isinstance(values, list):
                    _set_path(result, path, [item for item in values if not _matches_value(item, condition)])
        else:
            raise ValueError(f"Unsupported PostgreSQL document update operator: {operator}")
    return result


def _matches_value(value: Any, condition: Any) -> bool:
    if isinstance(condition, dict) and any(k.startswith("$") for k in condition):
        for op, expected in condition.items():
            if op == "$in" and value not in expected:
                return False
            if op == "$ne" and value == expected:
                return False
            if op not in ("$in", "$ne"):
                raise ValueError(f"Unsupported array update condition: {op}")
        return True
    return value == condition


class _Filter:
    def __init__(self, collection: str, query: dict, start: int = 1):
        self.collection = collection
        self.query = query or {}
        self.params: list[Any] = [collection]
        self.params.extend([None] * (start - 1))

    def param(self, value: Any, kind: str) -> str:
        if kind == "text[]":
            value = value.split(".")
        elif kind == "text":
            value = str(value)
        else:
            value = json.dumps(_encode(value), separators=(",", ":"))
        self.params.append(value)
        n = len(self.params)
        return f"${n}::{kind}"

    def compile(self) -> str:
        return f"collection = $1 AND ({self._compile(self.query)})"

    def _compile(self, query: dict) -> str:
        clauses = []
        for key, value in query.items():
            if key == "$or":
                clauses.append("(" + " OR ".join(self._compile(q) for q in value) + ")")
            elif key == "$and":
                clauses.append("(" + " AND ".join(self._compile(q) for q in value) + ")")
            elif key.startswith("$"):
                raise ValueError(f"Unsupported PostgreSQL document query operator: {key}")
            else:
                clauses.append(self._field(key, value))
        return " AND ".join(clauses) if clauses else "TRUE"

    def _field(self, path: str, condition: Any) -> str:
        expr = _path_sql(path)
        if not isinstance(condition, dict) or not any(k.startswith("$") for k in condition):
            return f"{expr} = {self.param(condition, 'jsonb')}"

        clauses = []
        for op, value in condition.items():
            if op == "$options":
                continue
            if op == "$exists":
                clauses.append(f"{expr} IS {'NOT ' if value else ''}NULL")
            elif op == "$ne":
                p = self.param(value, "jsonb")
                clauses.append(f"({expr} IS NULL OR {expr} <> {p})")
            elif op == "$in":
                p = self.param(value, "jsonb")
                clauses.append(f"EXISTS (SELECT 1 FROM jsonb_array_elements({p}) AS candidates(value) WHERE candidates.value = {expr})")
            elif op == "$nin":
                p = self.param(value, "jsonb")
                clauses.append(f"NOT EXISTS (SELECT 1 FROM jsonb_array_elements({p}) AS candidates(value) WHERE candidates.value = {expr})")
            elif op in ("$gt", "$gte", "$lt", "$lte"):
                p = self.param(value, "jsonb")
                token = {"$gt": ">", "$gte": ">=", "$lt": "<", "$lte": "<="}[op]
                clauses.append(f"{expr} {token} {p}")
            elif op == "$regex":
                p = self.param(value, "text")
                insensitive = "i" in str(condition.get("$options", ""))
                clauses.append(f"{_path_text_sql(path)} ~{'*' if insensitive else ''} {p}")
            else:
                raise ValueError(f"Unsupported PostgreSQL document query operator: {op}")
        return "(" + " AND ".join(clauses) + ")"


def _decode_record(row: asyncpg.Record | None) -> dict | None:
    if row is None:
        return None
    doc = _decode(json.loads(row["data"]))
    doc.setdefault("_id", row["doc_id"])
    return doc


class AsyncCursor:
    def __init__(self, collection: "AsyncCollection", query: dict, projection: dict | None):
        self.collection = collection
        self.query = query
        self.projection = projection
        self.order: list[tuple[str, int]] = []
        self.offset = 0
        self.max_rows: int | None = None

    def sort(self, order: list[tuple[str, int]] | tuple[tuple[str, int], ...]) -> "AsyncCursor":
        if isinstance(order, str):
            self.order = [(order, 1)]
        else:
            self.order = list(order)
        return self

    def skip(self, count: int) -> "AsyncCursor":
        self.offset = max(int(count), 0)
        return self

    def limit(self, count: int) -> "AsyncCursor":
        self.max_rows = max(int(count), 0)
        return self

    async def to_list(self, length: int | None = None) -> list[dict]:
        limit = self.max_rows
        if length is not None:
            limit = length if limit is None else min(limit, length)
        return await self.collection._find(self.query, self.projection, self.order, self.offset, limit)


class AsyncCollection:
    def __init__(self, database: "PostgresDatabase", name: str):
        self.database = database
        self.name = name

    def find(self, query: dict | None = None, projection: dict | None = None) -> AsyncCursor:
        return AsyncCursor(self, query or {}, projection)

    async def find_one(self, query: dict | None = None, projection: dict | None = None) -> dict | None:
        rows = await self._find(query or {}, projection, [], 0, 1)
        return rows[0] if rows else None

    async def _find(self, query: dict, projection: dict | None, order: list[tuple[str, int]],
                    offset: int, limit: int | None) -> list[dict]:
        where = _Filter(self.name, query)
        sql = f"SELECT doc_id, data FROM app_documents WHERE {where.compile()}"
        if order:
            terms = []
            for path, direction in order:
                terms.append(f"{_path_sql(path)} {'DESC' if direction < 0 else 'ASC'} NULLS LAST")
            sql += " ORDER BY " + ", ".join(terms)
        if limit is not None:
            sql += f" LIMIT {max(int(limit), 0)}"
        if offset:
            sql += f" OFFSET {max(int(offset), 0)}"
        async with self.database.pool.acquire() as conn:
            rows = await conn.fetch(sql, *where.params)
        docs = [_decode_record(row) for row in rows]
        return [_project(doc, projection) for doc in docs]

    async def count_documents(self, query: dict | None = None) -> int:
        where = _Filter(self.name, query or {})
        async with self.database.pool.acquire() as conn:
            return await conn.fetchval(f"SELECT count(*) FROM app_documents WHERE {where.compile()}", *where.params)

    async def insert_one(self, document: dict) -> InsertOneResult:
        doc = dict(document)
        doc.setdefault("_id", uuid.uuid4().hex)
        try:
            async with self.database.pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO app_documents (collection, doc_id, data) VALUES ($1, $2, $3::jsonb)",
                    self.name, str(doc["_id"]), json.dumps(_encode(doc), separators=(",", ":")),
                )
        except asyncpg.UniqueViolationError as exc:
            raise DuplicateKeyError(str(exc)) from exc
        return InsertOneResult(str(doc["_id"]))

    async def insert_many(self, documents: list[dict], ordered: bool = True) -> list[str]:
        ids = []
        duplicate = False
        async with self.database.pool.acquire() as conn:
            for document in documents:
                doc = dict(document)
                doc.setdefault("_id", uuid.uuid4().hex)
                try:
                    await conn.execute(
                        "INSERT INTO app_documents (collection, doc_id, data) VALUES ($1, $2, $3::jsonb)",
                        self.name, str(doc["_id"]), json.dumps(_encode(doc), separators=(",", ":")),
                    )
                    ids.append(str(doc["_id"]))
                except asyncpg.UniqueViolationError:
                    duplicate = True
                    if ordered:
                        raise DuplicateKeyError("Duplicate key in bulk insert")
        if duplicate:
            raise DuplicateKeyError("Duplicate key in bulk insert")
        return ids

    @_translate_unique_violation
    async def update_one(self, query: dict, update: dict, upsert: bool = False) -> WriteResult:
        where = _Filter(self.name, query or {})
        async with self.database.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    f"SELECT doc_id, data FROM app_documents WHERE {where.compile()} LIMIT 1 FOR UPDATE",
                    *where.params,
                )
                if row is None:
                    if not upsert:
                        return WriteResult()
                    doc = _equality_document(query or {})
                    doc = _apply_update(doc, update, inserting=True)
                    doc.setdefault("_id", uuid.uuid4().hex)
                    await conn.execute(
                        "INSERT INTO app_documents (collection, doc_id, data) VALUES ($1, $2, $3::jsonb)",
                        self.name, str(doc["_id"]), json.dumps(_encode(doc), separators=(",", ":")),
                    )
                    return WriteResult()
                old = _decode_record(row)
                changed = _apply_update(old, update)
                await conn.execute(
                    "UPDATE app_documents SET data = $3::jsonb WHERE collection = $1 AND doc_id = $2",
                    self.name, row["doc_id"], json.dumps(_encode(changed), separators=(",", ":")),
                )
                return WriteResult(1, int(changed != old))

    @_translate_unique_violation
    async def update_many(self, query: dict, update: dict) -> WriteResult:
        where = _Filter(self.name, query or {})
        async with self.database.pool.acquire() as conn:
            async with conn.transaction():
                rows = await conn.fetch(
                    f"SELECT doc_id, data FROM app_documents WHERE {where.compile()} FOR UPDATE",
                    *where.params,
                )
                modified = 0
                for row in rows:
                    old = _decode_record(row)
                    changed = _apply_update(old, update)
                    if changed != old:
                        await conn.execute(
                            "UPDATE app_documents SET data = $3::jsonb WHERE collection = $1 AND doc_id = $2",
                            self.name, row["doc_id"], json.dumps(_encode(changed), separators=(",", ":")),
                        )
                        modified += 1
                return WriteResult(len(rows), modified)

    @_translate_unique_violation
    async def find_one_and_update(self, query: dict, update: dict, return_document: ReturnDocument = ReturnDocument.BEFORE,
                                  upsert: bool = False) -> dict | None:
        where = _Filter(self.name, query or {})
        async with self.database.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    f"SELECT doc_id, data FROM app_documents WHERE {where.compile()} LIMIT 1 FOR UPDATE",
                    *where.params,
                )
                if row is None:
                    if not upsert:
                        return None
                    doc = _apply_update(_equality_document(query or {}), update, inserting=True)
                    doc.setdefault("_id", uuid.uuid4().hex)
                    await conn.execute(
                        "INSERT INTO app_documents (collection, doc_id, data) VALUES ($1, $2, $3::jsonb)",
                        self.name, str(doc["_id"]), json.dumps(_encode(doc), separators=(",", ":")),
                    )
                    return doc if return_document == ReturnDocument.AFTER else None
                old = _decode_record(row)
                changed = _apply_update(old, update)
                await conn.execute(
                    "UPDATE app_documents SET data = $3::jsonb WHERE collection = $1 AND doc_id = $2",
                    self.name, row["doc_id"], json.dumps(_encode(changed), separators=(",", ":")),
                )
                return changed if return_document == ReturnDocument.AFTER else old

    async def find_one_and_delete(self, query: dict) -> dict | None:
        where = _Filter(self.name, query or {})
        async with self.database.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    f"SELECT doc_id, data FROM app_documents WHERE {where.compile()} LIMIT 1 FOR UPDATE",
                    *where.params,
                )
                if row is None:
                    return None
                await conn.execute(
                    "DELETE FROM app_documents WHERE collection = $1 AND doc_id = $2",
                    self.name, row["doc_id"],
                )
                return _decode_record(row)

    async def delete_one(self, query: dict) -> WriteResult:
        where = _Filter(self.name, query or {})
        async with self.database.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    f"SELECT doc_id FROM app_documents WHERE {where.compile()} LIMIT 1 FOR UPDATE",
                    *where.params,
                )
                if row is None:
                    return WriteResult()
                await conn.execute(
                    "DELETE FROM app_documents WHERE collection = $1 AND doc_id = $2",
                    self.name, row["doc_id"],
                )
                return WriteResult(deleted_count=1)

    async def delete_many(self, query: dict) -> WriteResult:
        where = _Filter(self.name, query or {})
        async with self.database.pool.acquire() as conn:
            status = await conn.execute(f"DELETE FROM app_documents WHERE {where.compile()}", *where.params)
        return WriteResult(deleted_count=int(status.rsplit(" ", 1)[-1]))

    async def create_index(self, keys: str | list[tuple[str, int]], unique: bool = False,
                           sparse: bool = False, expireAfterSeconds: int | None = None, **_: Any) -> str:
        fields = [(keys, 1)] if isinstance(keys, str) else list(keys)
        signature = f"{self.name}:{fields}:{unique}:{sparse}:{expireAfterSeconds}"
        name = "idx_" + hashlib.sha1(signature.encode()).hexdigest()[:20]
        expressions = ", ".join(
            f"({_path_sql(field)}) {'DESC' if direction < 0 else 'ASC'}" for field, direction in fields
        )
        predicate = f"collection = '{self.name.replace(chr(39), chr(39) * 2)}'"
        if unique or sparse:
            for field, _ in fields:
                predicate += f" AND ({_path_sql(field)}) IS NOT NULL AND ({_path_sql(field)}) <> 'null'::jsonb"
        sql = (
            f"CREATE {'UNIQUE ' if unique else ''}INDEX IF NOT EXISTS {name} "
            f"ON app_documents ({expressions}) WHERE {predicate}"
        )
        async with self.database.pool.acquire() as conn:
            await conn.execute(sql)
        return name


class PostgresDatabase:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def command(self, name: str) -> dict:
        if name != "ping":
            raise ValueError(f"Unsupported PostgreSQL database command: {name}")
        async with self.pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"ok": 1}

    def __getattr__(self, name: str) -> AsyncCollection:
        if name.startswith("_"):
            raise AttributeError(name)
        return AsyncCollection(self, name)

    def __getitem__(self, name: str) -> AsyncCollection:
        return AsyncCollection(self, name)

    async def initialize(self) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS app_documents (
                    collection text NOT NULL,
                    doc_id text NOT NULL,
                    data jsonb NOT NULL,
                    PRIMARY KEY (collection, doc_id)
                )
                """
            )
            await conn.execute(
                "DELETE FROM app_documents WHERE collection = 'refresh_tokens' "
                "AND (data #>> '{expires_at}')::timestamp <= (now() AT TIME ZONE 'UTC')"
            )

    async def close(self) -> None:
        await self.pool.close()


def _equality_document(query: dict) -> dict:
    doc: dict = {}
    for path, value in query.items():
        if path.startswith("$") or (isinstance(value, dict) and any(k.startswith("$") for k in value)):
            continue
        _set_path(doc, path, value)
    return doc


def _project(doc: dict, projection: dict | None) -> dict:
    if not projection:
        return doc
    included = [path for path, flag in projection.items() if flag]
    if not included:
        result = dict(doc)
        for path, flag in projection.items():
            if not flag:
                _unset_path(result, path)
        return result
    result: dict = {}
    if projection.get("_id", 1) and "_id" in doc:
        result["_id"] = doc["_id"]
    for path in included:
        if path == "_id":
            continue
        value = _get_path(doc, path)
        if value is not None:
            _set_path(result, path, value)
    return result
