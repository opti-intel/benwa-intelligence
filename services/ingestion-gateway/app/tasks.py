"""Task CRUD endpoints — stores construction tasks in PostgreSQL."""

from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from shared.db import get_db

router = APIRouter(prefix="/tasks", tags=["tasks"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class TaskBase(BaseModel):
    naam: str
    beschrijving: str = ""
    status: str = "gepland"
    startdatum: Optional[str] = None
    einddatum: Optional[str] = None
    toegewezen_aan: str = ""


class TaskCreate(TaskBase):
    id: Optional[str] = None  # allow client-generated UUIDs


class TaskUpdate(TaskBase):
    pass


class TaskResponse(TaskBase):
    id: str

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("", response_model=list[TaskResponse])
async def list_tasks(
    status: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Return all tasks, optionally filtered by status."""
    if status:
        result = await db.execute(
            text("SELECT id, naam, beschrijving, status, startdatum::text, einddatum::text, toegewezen_aan FROM tasks WHERE status = :status ORDER BY startdatum ASC NULLS LAST"),
            {"status": status},
        )
    else:
        result = await db.execute(
            text("SELECT id, naam, beschrijving, status, startdatum::text, einddatum::text, toegewezen_aan FROM tasks ORDER BY startdatum ASC NULLS LAST"),
        )
    rows = result.mappings().all()
    return [
        TaskResponse(
            id=str(r["id"]),
            naam=r["naam"],
            beschrijving=r["beschrijving"] or "",
            status=r["status"],
            startdatum=r["startdatum"] or "",
            einddatum=r["einddatum"] or "",
            toegewezen_aan=r["toegewezen_aan"] or "",
        )
        for r in rows
    ]


@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(task: TaskCreate, db: AsyncSession = Depends(get_db)):
    """Create a new task."""
    task_id = task.id or str(uuid4())
    await db.execute(
        text("""
            INSERT INTO tasks (id, naam, beschrijving, status, startdatum, einddatum, toegewezen_aan)
            VALUES (:id, :naam, :beschrijving, :status, :startdatum, :einddatum, :toegewezen_aan)
        """),
        {
            "id": task_id,
            "naam": task.naam,
            "beschrijving": task.beschrijving,
            "status": task.status,
            "startdatum": task.startdatum or None,
            "einddatum": task.einddatum or None,
            "toegewezen_aan": task.toegewezen_aan,
        },
    )
    return TaskResponse(
        id=task_id,
        naam=task.naam,
        beschrijving=task.beschrijving,
        status=task.status,
        startdatum=task.startdatum or "",
        einddatum=task.einddatum or "",
        toegewezen_aan=task.toegewezen_aan,
    )


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(task_id: str, task: TaskUpdate, db: AsyncSession = Depends(get_db)):
    """Update an existing task."""
    result = await db.execute(
        text("""
            UPDATE tasks
            SET naam = :naam,
                beschrijving = :beschrijving,
                status = :status,
                startdatum = :startdatum,
                einddatum = :einddatum,
                toegewezen_aan = :toegewezen_aan,
                updated_at = NOW()
            WHERE id = :id
        """),
        {
            "id": task_id,
            "naam": task.naam,
            "beschrijving": task.beschrijving,
            "status": task.status,
            "startdatum": task.startdatum or None,
            "einddatum": task.einddatum or None,
            "toegewezen_aan": task.toegewezen_aan,
        },
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse(
        id=task_id,
        naam=task.naam,
        beschrijving=task.beschrijving,
        status=task.status,
        startdatum=task.startdatum or "",
        einddatum=task.einddatum or "",
        toegewezen_aan=task.toegewezen_aan,
    )


@router.delete("/{task_id}", status_code=204)
async def delete_task(task_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a task."""
    result = await db.execute(
        text("DELETE FROM tasks WHERE id = :id"),
        {"id": task_id},
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Task not found")
