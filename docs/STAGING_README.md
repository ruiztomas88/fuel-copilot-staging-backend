# 🚀 Fuel Copilot Staging - Mac Local Setup

## Estado Actual

✅ **Backend completamente funcional en tu Mac**
- Base de datos: `fuel_copilot_local`
- API: http://localhost:8000
- Data en tiempo real desde Wialon

---

## 📋 Servicios Corriendo

### 1. Wialon Sync Enhanced
- **Propósito**: Lee data de Wialon cada 15 segundos y guarda en `fuel_copilot_local`
- **Proceso**: `wialon_sync_enhanced.py`
- **Log**: `logs/wialon_sync.log`

### 2. FastAPI Backend
- **Propósito**: API REST para el frontend
- **Puerto**: 8000
- **Proceso**: `uvicorn main:app`
- **Log**: `logs/api.log`
- **Health Check**: http://localhost:8000/fuelAnalytics/api/health

---

## 🎮 Comandos

### Iniciar Servicios
```bash
cd /Users/tomasruiz/Desktop/Fuel-Analytics-Backend
./start_staging.sh
```

### Detener Servicios
```bash
./stop_staging.sh
```

### Verificar Estado
```bash
# Ver procesos
ps aux | grep -E "wialon_sync|uvicorn" | grep -v grep

# Test API
curl http://localhost:8000/fuelAnalytics/api/health

# Ver data reciente en BD
mysql -u root fuel_copilot_local -e "SELECT COUNT(*) as total, MAX(timestamp_utc) as latest FROM fuel_metrics WHERE DATE(timestamp_utc) = CURDATE()"
```

### Ver Logs en Tiempo Real
```bash
# Wialon Sync
tail -f logs/wialon_sync.log

# FastAPI
tail -f logs/api.log
```

---

## 🔄 Servicio Automático (LaunchAgent)

**Archivo**: `~/Library/LaunchAgents/com.fuelcopilot.staging.plist`

### Cargar servicio (auto-start al login)
```bash
launchctl load ~/Library/LaunchAgents/com.fuelcopilot.staging.plist
```

### Descargar servicio
```bash
launchctl unload ~/Library/LaunchAgents/com.fuelcopilot.staging.plist
```

### Ver estado del servicio
```bash
launchctl list | grep fuelcopilot
```

---

## 🔧 Arquitectura

```
[Wialon Remote DB] → [wialon_sync_enhanced.py] → [fuel_copilot_local MySQL]
                                                            ↓
                                                    [FastAPI Backend]
                                                            ↓
                                                    [Frontend - React]
```

### Diferencias vs Producción

| Aspecto | Staging (Mac) | Producción (VM) |
|---------|---------------|-----------------|
| Base de datos | `fuel_copilot_local` | `fuel_copilot` |
| Ubicación | Mac local | VM en la nube |
| Puerto API | 8000 | 8000 |
| Wialon source | Misma (wialon_collect) | Misma (wialon_collect) |
| Inicio | Manual o LaunchAgent | systemd |

---

## 📊 Verificación

### 1. Verificar Wialon Sync
```bash
# Debe mostrar ciclos cada 15 segundos
tail -20 logs/wialon_sync.log
```

Deberías ver:
```
2025-12-23 XX:XX:XX [INFO] ⏱️ Cycle completed in 0.3s. Trucks: 25, Records: 50
```

### 2. Verificar API
```bash
curl http://localhost:8000/fuelAnalytics/api/health
```

Deberías ver:
```json
{"status":"healthy","version":"4.0.0","trucks_available":27}
```

### 3. Verificar Data en BD
```bash
mysql -u root fuel_copilot_local -e "SELECT truck_id, timestamp_utc, truck_status FROM fuel_metrics ORDER BY timestamp_utc DESC LIMIT 5"
```

Deberías ver registros recientes (< 1 minuto).

---

## 🐛 Troubleshooting

### Servicios no inician
```bash
# Ver logs de LaunchAgent
cat logs/launchd.out
cat logs/launchd.err

# Reiniciar manualmente
./stop_staging.sh
./start_staging.sh
```

### Sin data nueva
```bash
# Ver último log de wialon sync
tail -50 logs/wialon_sync.log

# Verificar conexión a Wialon
mysql -u root wialon_collect -e "SELECT COUNT(*) FROM sensors LIMIT 1"
```

### API no responde
```bash
# Ver logs de API
tail -50 logs/api.log

# Verificar puerto
lsof -i :8000
```

---

## 🎯 Próximos Pasos

1. ✅ Backend local funcionando
2. ✅ Data en tiempo real de Wialon
3. ✅ Servicio automático configurado
4. ⏳ Conectar frontend a `http://localhost:8000`
5. ⏳ Probar ML features con data nueva

---

## 📝 Notas

- El staging usa la **misma fuente Wialon** que producción
- Los dos ambientes pueden correr **simultáneamente** sin conflictos
- La data se guarda en **bases de datos separadas**
- Los ML features están funcionando con data real
