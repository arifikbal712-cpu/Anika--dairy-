
from dotenv import load_dotenv
from pathlib import Path
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import os
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Literal

import bcrypt
import jwt
from fastapi import FastAPI, APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr, ConfigDict

MONGO_URL = os.environ['MONGO_URL']
DB_NAME = os.environ['DB_NAME']
JWT_SECRET = os.environ.get('JWT_SECRET', 'dev-secret-change-me')
JWT_ALG = "HS256"
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@example.com').lower()
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'Admin@123')

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

app = FastAPI(title="Anika Dairy API")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("anika")

security = HTTPBearer(auto_error=False)


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False


def create_token(email: str, role: str) -> str:
    payload = {"sub": email, "role": role,
               "exp": datetime.now(timezone.utc) + timedelta(days=7),
               "iat": datetime.now(timezone.utc)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


async def require_admin(creds: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> dict:
    if not creds or not creds.credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return payload


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def gen_order_id() -> str:
    return "AD" + datetime.now(timezone.utc).strftime("%y%m%d") + uuid.uuid4().hex[:5].upper()


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class Product(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    price: float
    unit: str
    image: str = ""
    category: str = "dairy"
    in_stock: bool = True
    created_at: str = Field(default_factory=now_iso)


class ProductIn(BaseModel):
    name: str
    description: str = ""
    price: float
    unit: str
    image: str = ""
    category: str = "dairy"
    in_stock: bool = True


class OrderItem(BaseModel):
    product_id: str
    name: str
    price: float
    quantity: int
    unit: str = ""


class OrderIn(BaseModel):
    customer_name: str
    phone: str
    address: str
    landmark: str = ""
    pincode: str
    delivery_slot: Literal["morning", "evening"]
    payment_method: Literal["cod", "upi"]
    items: List[OrderItem]
    notes: str = ""


class Order(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    order_id: str = Field(default_factory=gen_order_id)
    customer_name: str
    phone: str
    address: str
    landmark: str = ""
    pincode: str
    delivery_slot: str
    payment_method: str
    payment_status: str = "pending"
    items: List[OrderItem]
    subtotal: float
    delivery_charge: float
    total: float
    status: str = "pending"
    notes: str = ""
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class StatusUpdate(BaseModel):
    status: Literal["pending", "confirmed", "preparing", "out_for_delivery", "delivered", "cancelled"]


class Settings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    delivery_charge: float = 20.0
    min_order_amount: float = 100.0
    free_delivery_above: float = 500.0
    pincodes: List[str] = Field(default_factory=lambda: ["742135"])
    business_name: str = "Anika Dairy"
    phone: str = "+91 90000 00000"
    whatsapp: str = "+91 90000 00000"
    email: str = "arifikbal712@gmail.com"
    address: str = "Berhampore, Murshidabad, West Bengal, India"
    map_embed: str = "https://www.google.com/maps?q=Berhampore,Murshidabad&output=embed"
    time_slots: List[str] = Field(default_factory=lambda: ["Morning (6 AM - 9 AM)", "Evening (5 PM - 8 PM)"])
    upi_id: str = "arifikbal712@upi"
    tagline: str = "Fresh from our farm to your doorstep"


class SettingsIn(BaseModel):
    delivery_charge: Optional[float] = None
    min_order_amount: Optional[float] = None
    free_delivery_above: Optional[float] = None
    pincodes: Optional[List[str]] = None
    business_name: Optional[str] = None
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    map_embed: Optional[str] = None
    time_slots: Optional[List[str]] = None
    upi_id: Optional[str] = None
    tagline: Optional[str] = None


class Review(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    rating: int
    comment: str
    approved: bool = True
    created_at: str = Field(default_factory=now_iso)


class ReviewIn(BaseModel):
    name: str
    rating: int
    comment: str


DEFAULT_PRODUCTS = [
    {"name": "Fresh Milk", "description": "Farm-fresh cow milk, delivered daily. Pure, unadulterated, and pasteurized.", "price": 60.0, "unit": "per litre", "image": "https://images.unsplash.com/photo-1635436338433-89747d0ca0ef", "category": "milk"},
    {"name": "Fresh Curd", "description": "Thick, creamy homemade curd. Set fresh every morning from full-cream milk.", "price": 80.0, "unit": "per kg", "image": "https://images.pexels.com/photos/10809259/pexels-photo-10809259.jpeg", "category": "curd"},
    {"name": "Fresh Chana (Paneer)", "description": "Soft, fresh paneer made from pure cow milk. Perfect for curries and snacks.", "price": 350.0, "unit": "per kg", "image": "https://images.unsplash.com/photo-1661349008073-136bed6e6788?crop=entropy&cs=srgb&fm=jpg&q=85", "category": "paneer"},
]

DEFAULT_REVIEWS = [
    {"name": "Rakesh S.", "rating": 5, "comment": "Milk is always fresh and delivered on time. Best in town!"},
    {"name": "Priya M.", "rating": 5, "comment": "The paneer is so soft and tasty. My kids love it."},
    {"name": "Amit K.", "rating": 4, "comment": "Reliable service and honest quality. Highly recommended."},
]


async def seed_data():
    existing = await db.users.find_one({"email": ADMIN_EMAIL})
    if not existing:
        await db.users.insert_one({"id": str(uuid.uuid4()), "email": ADMIN_EMAIL, "password_hash": hash_password(ADMIN_PASSWORD), "role": "admin", "name": "Admin", "created_at": now_iso()})
    elif not verify_password(ADMIN_PASSWORD, existing.get("password_hash", "")):
        await db.users.update_one({"email": ADMIN_EMAIL}, {"$set": {"password_hash": hash_password(ADMIN_PASSWORD)}})

    if await db.products.count_documents({}) == 0:
        for p in DEFAULT_PRODUCTS:
            await db.products.insert_one(Product(**p).model_dump())

    if not await db.settings.find_one({"_id": "global"}):
        s = Settings().model_dump()
        s["_id"] = "global"
        await db.settings.insert_one(s)

    if await db.reviews.count_documents({}) == 0:
        for r in DEFAULT_REVIEWS:
            await db.reviews.insert_one(Review(**r).model_dump())


@app.on_event("startup")
async def on_startup():
    await db.users.create_index("email", unique=True)
    await db.products.create_index("id", unique=True)
    await db.orders.create_index("order_id", unique=True)
    await seed_data()


@app.on_event("shutdown")
async def on_shutdown():
    client.close()


@api.get("/")
async def root():
    return {"message": "Anika Dairy API", "status": "ok"}


@api.post("/auth/login")
async def login(payload: LoginIn):
    user = await db.users.find_one({"email": payload.email.lower()})
    if not user or not verify_password(payload.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_token(user["email"], user.get("role", "admin"))
    return {"token": token, "user": {"email": user["email"], "role": user.get("role", "admin"), "name": user.get("name", "Admin")}}


@api.get("/auth/me")
async def me(user=Depends(require_admin)):
    return {"email": user["sub"], "role": user["role"]}


@api.get("/products", response_model=List[Product])
async def list_products():
    return await db.products.find({}, {"_id": 0}).to_list(500)


@api.get("/settings")
async def get_settings():
    doc = await db.settings.find_one({"_id": "global"}, {"_id": 0})
    return doc or Settings().model_dump()


@api.get("/reviews", response_model=List[Review])
async def list_reviews():
    return await db.reviews.find({"approved": True}, {"_id": 0}).sort("created_at", -1).to_list(200)


@api.post("/reviews", response_model=Review)
async def add_review(payload: ReviewIn):
    if payload.rating < 1 or payload.rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be 1-5")
    r = Review(**payload.model_dump())
    await db.reviews.insert_one(r.model_dump())
    return r


@api.post("/orders")
async def create_order(payload: OrderIn):
    settings_doc = await db.settings.find_one({"_id": "global"}, {"_id": 0}) or Settings().model_dump()
    pincodes = settings_doc.get("pincodes", [])
    if pincodes and payload.pincode.strip() not in pincodes:
        raise HTTPException(status_code=400, detail=f"Sorry, we do not deliver to pincode {payload.pincode} yet.")
    if not payload.items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    products = {p["id"]: p for p in await db.products.find({}, {"_id": 0}).to_list(500)}
    subtotal = 0.0
    resolved: List[OrderItem] = []
    for it in payload.items:
        p = products.get(it.product_id)
        if not p:
            raise HTTPException(status_code=400, detail=f"Product not found: {it.product_id}")
        if not p.get("in_stock", True):
            raise HTTPException(status_code=400, detail=f"{p['name']} is out of stock")
        if it.quantity < 1:
            raise HTTPException(status_code=400, detail="Invalid quantity")
        subtotal += p["price"] * it.quantity
        resolved.append(OrderItem(product_id=p["id"], name=p["name"], price=p["price"], quantity=it.quantity, unit=p.get("unit", "")))

    min_order = float(settings_doc.get("min_order_amount", 0))
    if subtotal < min_order:
        raise HTTPException(status_code=400, detail=f"Minimum order amount is ₹{min_order:.0f}")

    delivery_charge = float(settings_doc.get("delivery_charge", 0))
    free_above = float(settings_doc.get("free_delivery_above", 0))
    if free_above > 0 and subtotal >= free_above:
        delivery_charge = 0.0
    total = subtotal + delivery_charge

    order = Order(customer_name=payload.customer_name, phone=payload.phone, address=payload.address,
                  landmark=payload.landmark, pincode=payload.pincode, delivery_slot=payload.delivery_slot,
                  payment_method=payload.payment_method, items=resolved,
                  subtotal=round(subtotal, 2), delivery_charge=round(delivery_charge, 2), total=round(total, 2),
                  notes=payload.notes)
    await db.orders.insert_one(order.model_dump())
    return {"order_id": order.order_id, "id": order.id, "total": order.total, "subtotal": order.subtotal,
            "delivery_charge": order.delivery_charge, "payment_method": order.payment_method,
            "status": order.status, "upi_id": settings_doc.get("upi_id", "")}


@api.get("/orders/track")
async def track_order(order_id: str, phone: str):
    doc = await db.orders.find_one({"order_id": order_id, "phone": phone}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Order not found. Check Order ID and phone number.")
    return doc


@api.get("/admin/orders", response_model=List[Order])
async def admin_list_orders(_=Depends(require_admin)):
    return await db.orders.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)


@api.put("/admin/orders/{order_id}/status")
async def admin_update_status(order_id: str, payload: StatusUpdate, _=Depends(require_admin)):
    res = await db.orders.update_one({"order_id": order_id}, {"$set": {"status": payload.status, "updated_at": now_iso()}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Order not found")
    return {"ok": True, "status": payload.status}


@api.post("/admin/products", response_model=Product)
async def admin_add_product(payload: ProductIn, _=Depends(require_admin)):
    p = Product(**payload.model_dump())
    await db.products.insert_one(p.model_dump())
    return p


@api.put("/admin/products/{product_id}", response_model=Product)
async def admin_update_product(product_id: str, payload: ProductIn, _=Depends(require_admin)):
    res = await db.products.update_one({"id": product_id}, {"$set": payload.model_dump()})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    return await db.products.find_one({"id": product_id}, {"_id": 0})


@api.delete("/admin/products/{product_id}")
async def admin_delete_product(product_id: str, _=Depends(require_admin)):
    res = await db.products.delete_one({"id": product_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"ok": True}


@api.put("/admin/settings")
async def admin_update_settings(payload: SettingsIn, _=Depends(require_admin)):
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    await db.settings.update_one({"_id": "global"}, {"$set": updates}, upsert=True)
    return await db.settings.find_one({"_id": "global"}, {"_id": 0})


@api.get("/admin/reviews", response_model=List[Review])
async def admin_list_reviews(_=Depends(require_admin)):
    return await db.reviews.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)


@api.delete("/admin/reviews/{review_id}")
async def admin_delete_review(review_id: str, _=Depends(require_admin)):
    res = await db.reviews.delete_one({"id": review_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Review not found")
    return {"ok": True}


app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=False,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)