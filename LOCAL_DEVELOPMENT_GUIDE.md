# 💻 DESARROLLO LOCAL EN MAC - STAGING WORKFLOW
**Tu Mac es tu staging environment - Más rápido, más seguro, mejor workflow**

---

## 🎯 CONCEPTO: Git como Staging

```
┌────────────────────────────────────────────────────────────┐
│                    TU WORKFLOW                             │
└────────────────────────────────────────────────────────────┘

1️⃣ DESARROLLO (Mac)
   ├── Backend local (localhost:8001)
   ├── Frontend local (localhost:5173)  
   ├── DB: Conecta a VM (read-only) O DB local
   └── Testear TODO localmente

2️⃣ COMMIT & PUSH (GitHub)
   ├── git add . && git commit
   ├── git push origin main
   └── GitHub almacena código testeado

3️⃣ DEPLOY (VM - Producción)
   ├── git pull origin main
   ├── Restart servicios
   └── Frontend: npm run build + deploy

┌────────────────────────────────────────────────────────────┐
│         NO NECESITAS STAGING SEPARADO EN VM                │
│         Tu Mac + GitHub ES tu staging                      │
└────────────────────────────────────────────────────────────┘
```

---

## 🚀 SETUP: Backend Local en Mac (15 min)

### Paso 1: Verificar que tienes el repo clonado

```bash
cd ~/Desktop/Fuel-Analytics-Backend
git status
```

✅ Ya lo tienes! No necesitas clonar nada nuevo.

---

### Paso 2: Crear .env LOCAL con acceso a VM

```bash
# Crear .env para desarrollo local
cd ~/Desktop/Fuel-Analytics-Backend
nano .env  # O usar VS Code
```

**Contenido de .env (Mac):**

```bash
# ============ DATABASE - CONECTAR A VM (READ-ONLY PARA SEGURIDAD) ============
# Opción A: Conectar a DB de producción en VM (SOLO LECTURA)
DB_HOST=20.127.200.135
DB_PORT=3306
DB_USER=consult_user  # Usuario con permisos SOLO lectura
DB_PASSWORD=C0nsult_2024!
DB_NAME=fuel_copilot

# Opción B: DB local en Mac para testing (recomendado si haces INSERTS)
# DB_HOST=localhost
# DB_PORT=3306
# DB_USER=root
# DB_PASSWORD=tu_password_mysql_local
# DB_NAME=fuel_copilot_local

# ============ WIALON DB (Conectar a VM remoto) ============
WIALON_DB_HOST=20.127.200.135
WIALON_DB_PORT=3306
WIALON_DB_USER=consult_user
WIALON_DB_PASSWORD=C0nsult_2024!
WIALON_DB_NAME=wialon

# ============ API LOCAL ============
API_PORT=8001
API_HOST=0.0.0.0
API_BASE_URL=http://localhost:8001

# ============ ENVIRONMENT ============
ENVIRONMENT=development
DEBUG=True

# ============ FEATURES (para testing) ============
# Desactivar features que no quieres probar localmente
SEND_EMAILS=False  # No enviar emails reales en desarrollo
SEND_SMS=False     # No enviar SMS reales
ENABLE_ALERTS=False  # No crear alertas reales

# ============ TWILIO (opcional en dev) ============
TWILIO_ACCOUNT_SID=tu_sid
TWILIO_AUTH_TOKEN=tu_token
TWILIO_PHONE_NUMBER=+1234567890

# ============ SMTP (opcional en dev) ============
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=tu_email@gmail.com
SMTP_PASSWORD=tu_password
```

---

### Paso 3: Instalar dependencias (si no las tienes)

```bash
cd ~/Desktop/Fuel-Analytics-Backend

# Crear virtualenv si no existe
python3 -m venv venv

# Activar virtualenv
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Instalar dependencias de testing (si no están)
pip install pytest pytest-cov pytest-mock faker hypothesis
```

---

### Paso 4: OPCIÓN A - Conectar a DB Remota (VM)

**Ventajas:**
- ✅ Datos reales inmediatos
- ✅ No necesitas copiar nada
- ✅ Testing con datos actuales

**Desventajas:**
- ❌ Requiere acceso a VM
- ❌ Si haces INSERT/UPDATE afecta producción (⚠️ PELIGRO)

**Solución Segura:** Crear usuario READ-ONLY en VM

```powershell
# En VM (ejecutar como admin):
$env:MYSQL_PWD='FuelCopilot2025!'
mysql -u fuel_admin -e "
  CREATE USER IF NOT EXISTS 'dev_readonly'@'%' IDENTIFIED BY 'DevReadOnly2025!';
  GRANT SELECT ON fuel_copilot.* TO 'dev_readonly'@'%';
  GRANT SELECT ON wialon.* TO 'dev_readonly'@'%';
  FLUSH PRIVILEGES;
"
```

**Luego en Mac (.env):**
```bash
DB_HOST=20.127.200.135
DB_USER=dev_readonly  # ← Usuario con SOLO lectura
DB_PASSWORD=DevReadOnly2025!
DB_NAME=fuel_copilot
```

---

### Paso 5: OPCIÓN B - DB Local en Mac (RECOMENDADO para desarrollo)

**Ventajas:**
- ✅ Puedes hacer INSERT/UPDATE sin miedo
- ✅ Testing completo sin afectar producción
- ✅ Más rápido (sin latencia de red)

**Desventajas:**
- ❌ Necesitas copiar datos iniciales

**Setup:**

```bash
# 1. Instalar MySQL en Mac (si no lo tienes)
brew install mysql
brew services start mysql

# 2. Configurar password
mysql_secure_installation

# 3. Crear base de datos local
mysql -u root -p
```

```sql
CREATE DATABASE fuel_copilot_local CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE fuel_copilot_local;

-- Copiar estructura de producción (lo veremos abajo)
```

**Copiar datos de VM a Mac:**

```bash
# En Mac: Conectar a VM y exportar datos recientes
ssh devteam@20.127.200.135

# En VM: Exportar últimos 7 días
mysqldump -u fuel_admin -p \
  --where="timestamp_utc > DATE_SUB(NOW(), INTERVAL 7 DAY)" \
  fuel_copilot fuel_metrics > /tmp/fuel_metrics_sample.sql

mysqldump -u fuel_admin -p fuel_copilot trucks > /tmp/trucks.sql
mysqldump -u fuel_admin -p fuel_copilot refuel_events > /tmp/refuel_events.sql

# Copiar archivos a Mac
scp devteam@20.127.200.135:/tmp/*.sql ~/Desktop/

# En Mac: Importar
mysql -u root -p fuel_copilot_local < ~/Desktop/fuel_metrics_sample.sql
mysql -u root -p fuel_copilot_local < ~/Desktop/trucks.sql  
mysql -u root -p fuel_copilot_local < ~/Desktop/refuel_events.sql
```

---

### Paso 6: Correr Backend Localmente

```bash
cd ~/Desktop/Fuel-Analytics-Backend
source venv/bin/activate

# Opción 1: Correr API solo (para testing de endpoints)
python api_v2.py

# Opción 2: Correr WialonSync (para testing de sync completo)
python wialon_sync_enhanced.py

# Opción 3: Correr ambos en terminales separadas
# Terminal 1:
python api_v2.py

# Terminal 2:
python wialon_sync_enhanced.py
```

**Verificar que funciona:**
```bash
# Abrir otra terminal
curl http://localhost:8001/api/health
# Debe responder: {"status":"ok"}

# Ver trucks
curl http://localhost:8001/api/trucks | jq

# Ver latest metrics
curl http://localhost:8001/api/metrics/latest | jq
```

---

## 🎨 FRONTEND: Conectar a Backend Local

### Paso 1: Modificar .env del frontend

```bash
cd ~/Desktop/Fuel-Analytics-Frontend
nano .env  # O usar VS Code
```

**Contenido:**
```bash
# Para desarrollo local
VITE_API_BASE_URL=http://localhost:8001
VITE_ENVIRONMENT=development
```

### Paso 2: Correr frontend

```bash
npm run dev
```

**Abrir:** http://localhost:5173

✅ Ahora el dashboard carga datos de tu backend local!

---

## 🔄 WORKFLOW DE DESARROLLO

### Escenario 1: Implementar Benchmarking Engine

```bash
# 1. Crear feature branch
cd ~/Desktop/Fuel-Analytics-Backend
git checkout -b feature/benchmarking-engine

# 2. Crear archivo nuevo
nano benchmarking_engine.py
# (escribir código)

# 3. Crear tests
nano test_benchmarking.py
# (escribir tests)

# 4. Correr tests LOCALMENTE
pytest test_benchmarking.py -v

# 5. Si pasan → integrar en API
nano api_v2.py
# Agregar endpoint: /api/benchmarks/truck/{truck_id}

# 6. Probar endpoint local
python api_v2.py
# En otra terminal:
curl http://localhost:8001/api/benchmarks/truck/RA9250 | jq

# 7. Si funciona → correr todos los tests
pytest tests/ -v --cov=.

# 8. Si todo pasa → commit
git add benchmarking_engine.py test_benchmarking.py api_v2.py
git commit -m "feat: Add benchmarking engine with full tests"

# 9. Push a GitHub
git push origin feature/benchmarking-engine

# 10. Crear Pull Request en GitHub
# Revisar, aprobar, merge a main

# 11. Deploy a VM (producción)
```

---

### Escenario 2: Deploy a Producción (VM)

```powershell
# En VM (después de merge a main):
cd C:\Users\devteam\Proyectos\fuel-analytics-backend

# Pull latest
git pull origin main

# Restart servicios
Restart-Service FuelAnalytics-API
Restart-Service FuelAnalytics-WialonSync

# Verificar logs
Get-Content logs\wialon-sync-stderr.log -Tail 50
```

**Frontend Deploy:**
```bash
# En Mac
cd ~/Desktop/Fuel-Analytics-Frontend

# Asegurarte que .env apunta a producción
cat .env
# VITE_API_BASE_URL=https://fleetbooster.net/fuelAnalytics

# Build
npm run build

# Deploy a Azure/Netlify/Vercel (según donde esté)
# Si usas Azure Static Web Apps:
# npm run deploy
# O manual: subir carpeta dist/ a Azure portal
```

---

## 🧪 TESTING WORKFLOW

### 1. Unit Tests (rápidos, sin DB)

```python
# test_benchmarking.py
import pytest
from benchmarking_engine import BenchmarkingEngine

def test_calculate_benchmark():
    engine = BenchmarkingEngine()
    result = engine.calculate_mpg_benchmark(
        truck_id="RA9250",
        peer_data=[6.5, 7.2, 6.8, 7.0]  # Mock data
    )
    
    assert result.benchmark_mpg == 6.875  # Mediana
    assert result.percentile > 0
    assert result.percentile < 100

def test_handles_no_peers():
    engine = BenchmarkingEngine()
    result = engine.calculate_mpg_benchmark(
        truck_id="UNIQUE_TRUCK",
        peer_data=[]
    )
    
    assert result.benchmark_mpg is None
    assert result.confidence == 0
```

**Correr:**
```bash
pytest test_benchmarking.py -v
```

---

### 2. Integration Tests (requieren DB)

```python
# test_benchmarking_integration.py
import pytest
from benchmarking_engine import BenchmarkingEngine
from database import get_db_connection

@pytest.fixture
def db_connection():
    """Conectar a DB local de testing"""
    conn = get_db_connection()
    yield conn
    conn.close()

def test_benchmarking_with_real_data(db_connection):
    """Test con datos reales de DB"""
    engine = BenchmarkingEngine(db_connection)
    
    # Usar truck real de DB
    result = engine.calculate_mpg_benchmark(truck_id="RA9250", period_days=7)
    
    assert result is not None
    assert result.benchmark_mpg > 0
    assert len(result.peers) > 0
    
    # Verificar que no crashea con datos reales
    print(f"Benchmark MPG: {result.benchmark_mpg}")
    print(f"Peers encontrados: {len(result.peers)}")
```

**Correr:**
```bash
# Asegurarte que .env apunta a DB local o read-only remota
pytest test_benchmarking_integration.py -v
```

---

### 3. Performance Tests

```python
# test_benchmarking_performance.py
import pytest
import time
from benchmarking_engine import BenchmarkingEngine

def test_benchmark_calculation_speed():
    """Benchmark debe calcular en <1 segundo"""
    engine = BenchmarkingEngine()
    
    start = time.time()
    result = engine.calculate_mpg_benchmark("RA9250", period_days=30)
    elapsed = time.time() - start
    
    assert elapsed < 1.0, f"Demasiado lento: {elapsed:.2f}s"
    print(f"✅ Benchmark calculado en {elapsed:.2f}s")
```

---

## 🎯 VENTAJAS DE ESTE WORKFLOW

### ✅ Desarrollo Local (Mac)
- **Velocidad:** Cambios instantáneos, no esperar deploy
- **Debugging:** Breakpoints, print statements, fácil
- **Experimentación:** Probar ideas sin consecuencias
- **Tests:** Correr 100 veces sin afectar nada

### ✅ Git como Staging
- **Historial:** Todo cambio documentado
- **Rollback:** git revert fácil
- **Colaboración:** Pull requests, code review
- **CI/CD:** GitHub Actions puede correr tests automáticamente

### ✅ VM como Producción
- **Estable:** Solo recibe código probado
- **Mínimo downtime:** Solo git pull + restart
- **Monitoreo:** Logs claros, métricas reales

---

## 🚧 CASOS ESPECIALES

### Caso 1: Feature requiere datos que no tienes localmente

**Opción A:** Conectar a DB remota (read-only)
```bash
# .env
DB_HOST=20.127.200.135
DB_USER=dev_readonly
```

**Opción B:** Copiar dataset específico
```bash
# Exportar solo lo que necesitas
mysqldump -u fuel_admin -p \
  --where="truck_id IN ('RA9250','FF7702')" \
  fuel_copilot fuel_metrics > sample_data.sql
  
# Importar en local
mysql -u root -p fuel_copilot_local < sample_data.sql
```

---

### Caso 2: Probar con dashboard online antes de deploy final

**Opción A:** Exponer tu Mac temporalmente (ngrok)
```bash
# Instalar ngrok
brew install ngrok

# Exponer puerto 8001
ngrok http 8001

# Obtienes URL: https://abc123.ngrok.io
# Modificar frontend .env temporalmente:
VITE_API_BASE_URL=https://abc123.ngrok.io

# Ahora puedes acceder desde cualquier lugar!
```

**Opción B:** Deploy temporal a staging en VM
- Seguir guía STAGING_ENVIRONMENT_SETUP.md
- Solo si realmente necesitas

---

### Caso 3: Testing de WialonSync completo (24h)

Si necesitas probar wialon_sync_enhanced.py por 24h:

**Opción A:** Correr en Mac durante la noche
```bash
# Terminal que no cierras
cd ~/Desktop/Fuel-Analytics-Backend
source venv/bin/activate
python wialon_sync_enhanced.py

# Dejar corriendo overnight
# Revisar logs en la mañana
```

**Opción B:** Deploy temporal a VM staging
- Ver STAGING_ENVIRONMENT_SETUP.md

---

## 📋 CHECKLIST: Antes de Deploy a Producción

- [ ] Tests unitarios pasan (pytest tests/unit/ -v)
- [ ] Tests integración pasan (pytest tests/integration/ -v)
- [ ] Probado localmente con datos reales
- [ ] Frontend local funciona con backend local
- [ ] No hay breaking changes (código viejo sigue funcionando)
- [ ] Performance aceptable (<1s para queries)
- [ ] Documentación actualizada
- [ ] CHANGELOG.md actualizado
- [ ] Commit message descriptivo
- [ ] Push a GitHub exitoso
- [ ] (Opcional) Pull Request revisado y aprobado

**Solo entonces:**
```powershell
# En VM
git pull origin main
Restart-Service FuelAnalytics-*
```

---

## 🎓 RESUMEN: Tu Workflow Ideal

```
┌─────────────────────────────────────────────────────────┐
│ 1. DESARROLLAR en Mac                                   │
│    ├── Backend local (localhost:8001)                   │
│    ├── Frontend local (localhost:5173)                  │
│    ├── DB local O read-only remota                      │
│    └── Tests completos (pytest)                         │
│                                                          │
│ 2. COMMIT cuando funciona                               │
│    ├── git add .                                        │
│    ├── git commit -m "feat: ..."                        │
│    └── git push origin main                             │
│                                                          │
│ 3. DEPLOY a VM (producción)                             │
│    ├── git pull origin main                             │
│    ├── Restart servicios                                │
│    └── Monitor logs 15 min                              │
│                                                          │
│ 4. FRONTEND deploy                                      │
│    ├── npm run build                                    │
│    └── Deploy a Azure/Netlify/Vercel                    │
└─────────────────────────────────────────────────────────┘

NO NECESITAS staging separado en VM!
Tu Mac ES tu staging environment.
```

---

## 🚀 PRÓXIMO PASO: Setup Rápido Ahora

```bash
# 1. Verificar que tienes MySQL en Mac
mysql --version

# 2. Si no tienes, instalar:
brew install mysql
brew services start mysql

# 3. Crear .env en backend
cd ~/Desktop/Fuel-Analytics-Backend
# Copiar ejemplo de arriba

# 4. Activar virtualenv e instalar deps
source venv/bin/activate
pip install -r requirements.txt

# 5. Probar que funciona
python api_v2.py
# En otra terminal:
curl http://localhost:8001/api/health

# ✅ Listo! Ya puedes desarrollar
```

---

*Local Development Guide - v1.0 - 23 Dic 2025*
