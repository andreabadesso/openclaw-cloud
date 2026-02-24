from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from openclaw_api.deps import get_db
from openclaw_api.models import Bundle
from openclaw_api.schemas import (
    BundleListItem,
    BundleListResponse,
    BundleResponse,
    CreateBundleRequest,
    UpdateBundleRequest,
)

router = APIRouter(tags=["bundles"])


# --- Public endpoints ---


@router.get("/bundles", response_model=BundleListResponse)
async def list_published_bundles(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Bundle)
        .where(Bundle.status == "published")
        .order_by(Bundle.sort_order, Bundle.name)
    )
    bundles = result.scalars().all()
    return BundleListResponse(bundles=[BundleListItem.model_validate(b) for b in bundles])


@router.get("/bundles/{slug}", response_model=BundleResponse)
async def get_bundle(slug: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Bundle).where(Bundle.slug == slug))
    bundle = result.scalar_one_or_none()
    if not bundle:
        raise HTTPException(status_code=404, detail="Bundle not found")
    if bundle.status != "published":
        raise HTTPException(status_code=404, detail="Bundle not found")
    return BundleResponse.model_validate(bundle)


# --- Admin endpoints ---


@router.get("/internal/bundles", response_model=list[BundleResponse])
async def list_all_bundles(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Bundle).order_by(Bundle.sort_order, Bundle.name)
    )
    bundles = result.scalars().all()
    return [BundleResponse.model_validate(b) for b in bundles]


@router.post("/internal/bundles", response_model=BundleResponse, status_code=201)
async def create_bundle(body: CreateBundleRequest, db: AsyncSession = Depends(get_db)):
    # Check slug uniqueness
    existing = await db.execute(select(Bundle).where(Bundle.slug == body.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Bundle slug already exists")

    bundle = Bundle(
        slug=body.slug,
        name=body.name,
        description=body.description,
        icon=body.icon,
        color=body.color,
        status=body.status,
        prompts=body.prompts,
        default_model=body.default_model,
        default_thinking_level=body.default_thinking_level,
        default_language=body.default_language,
        providers=[p.model_dump() for p in body.providers],
        mcp_servers=body.mcp_servers,
        skills=body.skills,
        sort_order=body.sort_order,
    )
    db.add(bundle)
    await db.commit()
    await db.refresh(bundle)
    return BundleResponse.model_validate(bundle)


@router.patch("/internal/bundles/{bundle_id}", response_model=BundleResponse)
async def update_bundle(
    bundle_id: str,
    body: UpdateBundleRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Bundle).where(Bundle.id == bundle_id))
    bundle = result.scalar_one_or_none()
    if not bundle:
        raise HTTPException(status_code=404, detail="Bundle not found")

    updates = body.model_dump(exclude_none=True)
    if "providers" in updates:
        updates["providers"] = [p.model_dump() for p in body.providers]
    for key, value in updates.items():
        setattr(bundle, key, value)

    await db.commit()
    await db.refresh(bundle)
    return BundleResponse.model_validate(bundle)


@router.delete("/internal/bundles/{bundle_id}", status_code=204)
async def archive_bundle(bundle_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Bundle).where(Bundle.id == bundle_id))
    bundle = result.scalar_one_or_none()
    if not bundle:
        raise HTTPException(status_code=404, detail="Bundle not found")
    bundle.status = "archived"
    await db.commit()
