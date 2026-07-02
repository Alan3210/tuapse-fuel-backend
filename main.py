from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, Session, declarative_base

# --- НАСТРОЙКИ БАЗЫ ДАННЫХ ---
# Сейчас это SQLite. Позже мы заменим эту строку на ссылку от твоего Supabase (postgresql://...)
SQLALCHEMY_DATABASE_URL = "postgresql://postgres:TuapseFuel2026@db.ssidiyuiayozpzzqevkr.supabase.co:5432/postgres"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- МОДЕЛЬ ТАБЛИЦЫ В БАЗЕ ДАННЫХ ---
class DBStation(Base):
    __tablename__ = "stations"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    address = Column(String)
    fuel_92 = Column(String, default="UNKNOWN")
    fuel_95 = Column(String, default="UNKNOWN")
    fuel_dt = Column(String, default="UNKNOWN")
    queue = Column(String, default="UNKNOWN")
    alert = Column(String, default="")
    updated_at = Column(String, default="Давно")

# --- СТАНДАРТНАЯ ИНИЦИАЛИЗАЦИЯ APP ---
app = FastAPI(title="Tuapse Fuel Radar API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ПЕРВИЧНАЯ ЗАГРУЗКА ДАННЫХ (9 ЗАПРАВОК) ---
INITIAL_STATIONS = [
    {"id": 1, "name": "Роснефть (Бондаренко, 59)", "address": "Туапсе, ул. Бондаренко, 59", "fuel": {"92": "LIMITED", "95": "LIMITED", "dt": "LIMITED"}, "queue": "TABLO", "alert": "Лимит 30л. Очередь 20-30 машин!", "updatedAt": "Только что"},
    {"id": 2, "name": "Роснефть (Говорова нижняя)", "address": "Туапсе, ул. Говорова (низ)", "fuel": {"92": "UNKNOWN", "95": "UNKNOWN", "dt": "UNKNOWN"}, "queue": "UNKNOWN", "alert": "", "updatedAt": "15 мин назад"},
    {"id": 3, "name": "Роснефть (Говорова верхняя)", "address": "Туапсе, ул. Говорова (верх)", "fuel": {"92": "EMPTY", "95": "EMPTY", "dt": "EMPTY"}, "queue": "NONE", "alert": "⚠️ Флажки натянули (Закрыто)", "updatedAt": "Только что"},
    {"id": 4, "name": "Роснефть (Магри)", "address": "пост Магри, трасса А-147", "fuel": {"92": "LIMITED", "95": "LIMITED", "dt": "LIMITED"}, "queue": "FEW", "alert": "Ограничение 30л (если не палить канистру, нальют)", "updatedAt": "10 мин назад"},
    {"id": 5, "name": "Лукойл (Магри)", "address": "пост Магри, трасса А-147", "fuel": {"92": "AVAILABLE", "95": "AVAILABLE", "dt": "AVAILABLE"}, "queue": "FEW", "alert": "", "updatedAt": "1 час назад"},
    {"id": 6, "name": "Роснефть (Агой)", "address": "Агой, трасса А-147", "fuel": {"92": "DRAIN", "95": "AVAILABLE", "dt": "AVAILABLE"}, "queue": "TABLO", "alert": "⚠️ Работает 3 колонки! Слив 92-го, всё стоит на час. Хвост на трассе.", "updatedAt": "Только что"},
    {"id": 7, "name": "Газпром (Агой)", "address": "Агой, трасса А-147", "fuel": {"92": "UNKNOWN", "95": "UNKNOWN", "dt": "UNKNOWN"}, "queue": "UNKNOWN", "alert": "", "updatedAt": "3 часа назад"},
    {"id": 8, "name": "Лукойл (Ольгинка)", "address": "Ольгинка, трасса А-147", "fuel": {"92": "AVAILABLE", "95": "EMPTY", "dt": "EMPTY"}, "queue": "NONE", "alert": "Только 92 и 100-й бензин", "updatedAt": "20 мин назад"},
    {"id": 9, "name": "АЗС АТП (Кривая)", "address": "Туапсе, Кривая", "fuel": {"92": "UNKNOWN", "95": "UNKNOWN", "dt": "UNKNOWN"}, "queue": "UNKNOWN", "alert": "Ждем информацию...", "updatedAt": "Давно"}
]

@app.on_event("startup")
def startup_populate_db():
    # Создаем таблицу в базе, если ее нет
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    # Если база пустая, заливаем туда наши заправки
    if db.query(DBStation).count() == 0:
        for st in INITIAL_STATIONS:
            new_st = DBStation(
                id=st["id"], name=st["name"], address=st["address"],
                fuel_92=st["fuel"]["92"], fuel_95=st["fuel"]["95"], fuel_dt=st["fuel"]["dt"],
                queue=st["queue"], alert=st["alert"], updated_at=st["updatedAt"]
            )
            db.add(new_st)
        db.commit()
    db.close()

# Зависимость для подключения к БД
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- МОДЕЛЬ ДАННЫХ (ОТ ФРОНТЕНДА) ---
class Report(BaseModel):
    station_id: int
    fuel_92: str
    fuel_95: str
    fuel_dt: str
    queue: str

# --- API МЕТОДЫ ---
@app.get("/api/stations")
async def get_stations(db: Session = Depends(get_db)):
    # Достаем все заправки из базы
    db_stations = db.query(DBStation).all()
    # Переупаковываем их в формат, который ждет наш Фронтенд (React)
    result = []
    for s in db_stations:
        result.append({
            "id": s.id,
            "name": s.name,
            "address": s.address,
            "fuel": {"92": s.fuel_92, "95": s.fuel_95, "dt": s.fuel_dt},
            "queue": s.queue,
            "alert": s.alert,
            "updatedAt": s.updated_at
        })
    return result

@app.post("/api/reports")
async def submit_report(report: Report, db: Session = Depends(get_db)):
    # Ищем заправку в базе
    station = db.query(DBStation).filter(DBStation.id == report.station_id).first()
    if not station:
        return {"status": "error", "message": "Заправка не найдена"}
    
    # Обновляем данные прямо в базе
    station.fuel_92 = report.fuel_92
    station.fuel_95 = report.fuel_95
    station.fuel_dt = report.fuel_dt
    station.queue = report.queue
    
    # Авто-алерт при сливе
    if "DRAIN" in [report.fuel_92, report.fuel_95, report.fuel_dt]:
        station.alert = "⚠️ Идет слив бензовоза!"
    else:
        station.alert = ""
        
    station.updated_at = "Только что"
    
    # Сохраняем изменения на диск
    db.commit()
    
    return {"status": "success", "message": "Статус сохранен в Базе Данных!"}