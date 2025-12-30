# Fuel Analytics - Gestión de Servicios

## ✅ RESUMEN DE LO REALIZADO (Dic 29, 2025)

### Problemas Solucionados

1. **Error "Circular reference detected"** en endpoint de camiones
   - **Causa**: El router en `routers/trucks_router.py` usaba un lambda que no manejaba todos los tipos de datos numpy/pandas
   - **Solución**: Implementada sanitización completa con conversión de numpy/pandas a tipos nativos Python
   - **Archivos modificados**: `routers/trucks_router.py` líneas 90-151

2. **LaunchD servicios fallando** con error 78
   - **Causa**: Restricciones de macOS con launchd (permisos, workingDirectory, etc)
   - **Solución**: Eliminados todos los servicios launchd, sistema manual con logging detallado
   - **Archivos eliminados**: Todos los `.plist` en `~/Library/LaunchAgents/com.fuelanalytics.*`

3. **Lentitud en carga del Dashboard**
   - **Causa**: Múltiples componentes haciendo requests duplicados al endpoint `/fleet` sin caché compartido
   - **Solución**: Implementado sistema de caché en memoria con TTL de 5 segundos
   - **Archivos modificados**: `src/hooks/useApi.ts` líneas 77-158

### Performance Actual

| Endpoint | Tiempo de Respuesta |
|----------|---------------------|
| `/api/trucks/{id}` | ~11ms |
| `/api/trucks/{id}/history` | ~14ms |
| `/api/trucks/{id}/refuels` | ~2.5ms |
| `/api/fleet` | ~1.2ms |
| `/api/efficiency` | ~7.5ms |
| `/api/refuels` | ~24ms |
| `/api/alerts` | ~176ms ⚠️ |

⚠️ **Nota**: El endpoint `/alerts` es el más lento (176ms), podría necesitar optimización futura.

---

## 📋 INICIO DE SERVICIOS

### Método Recomendado: Script Automático

```bash
bash /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/services/start_with_logs.sh
```

Este script:
- ✅ Verifica dependencias
- ✅ Inicia Wialon Sync, Backend API y Frontend
- ✅ Genera logs detallados con timestamp
- ✅ Verifica que cada servicio arranque correctamente
- ✅ Muestra resumen final con URLs y comandos útiles

### Logs Generados

Cada vez que inicias los servicios, se generan logs únicos:

```
logs/wialon_YYYYMMDD_HHMMSS.log
logs/backend_YYYYMMDD_HHMMSS.log
logs/frontend_YYYYMMDD_HHMMSS.log
```

---

## 🔍 MONITOREO EN TIEMPO REAL

### Ver logs en tiempo real:

```bash
# Backend
tail -f /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/logs/backend_*.log

# Frontend  
tail -f /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/logs/frontend_*.log

# Wialon
tail -f /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/logs/wialon_*.log
```

### Buscar errores:

```bash
# Errores en backend (últimos 50)
grep -i "error\|exception\|critical" logs/backend_*.log | tail -50

# Errores en frontend
grep -i "error\|failed" logs/frontend_*.log | grep -v node_modules | tail -30
```

### Ver procesos activos:

```bash
ps aux | grep -E "(main.py|wialon_sync|vite)" | grep -v grep
```

---

## 🛑 DETENER SERVICIOS

### Detener todos los servicios:

```bash
bash /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/services/stop_all_services.sh
```

O manualmente:

```bash
pkill -f "python.*main.py"
pkill -f "wialon_sync"
pkill -f "vite.*dev"
```

---

## 🔧 TROUBLESHOOTING

### Problema: Backend no arranca

```bash
# Ver últimas 30 líneas del log más reciente
tail -30 logs/backend_*.log | tail -30

# Verificar puerto 8000 libre
lsof -i :8000

# Matar proceso que ocupe el puerto
kill -9 $(lsof -ti:8000)
```

### Problema: Frontend no carga

```bash
# Ver log del frontend
tail -50 logs/frontend_*.log

# Verificar puertos comunes
lsof -i :3000 -i :3001 -i :5173

# Limpiar caché de npm
cd /Users/tomasruiz/Desktop/Fuel-Analytics-Frontend
rm -rf node_modules/.vite
```

### Problema: "Circular reference detected" reaparece

Este error indica que hay objetos complejos (numpy, pandas, clases personalizadas) en la respuesta del API.

**Solución**:
1. Verificar logs del backend cuando ocurre el error
2. Buscar línea con `[get_truck_detail]` 
3. El log mostrará qué campo específico causó el problema
4. Agregar conversión explícita para ese tipo de dato en `routers/trucks_router.py`

---

## 📊 VERIFICACIÓN DE SALUD

### Health Check Manual:

```bash
# Backend
curl http://localhost:8000/health | python3 -m json.tool

# Endpoint de camión (ejemplo)
curl http://localhost:8000/fuelAnalytics/api/trucks/DO9693 | head -5

# Frontend (debe devolver HTML)
curl http://localhost:3000 2>&1 | grep "<title>"
```

### URLs Principales:

- **Backend API**: http://localhost:8000
- **API Docs (Swagger)**: http://localhost:8000/docs
- **Frontend**: http://localhost:3000 (o puerto dinámico detectado)
- **Health Check**: http://localhost:8000/health

---

## 💡 OPTIMIZACIONES IMPLEMENTADAS

### 1. Caché en Memoria (useFleetSummary)

**Antes**: Cada componente hacía su propio request a `/api/fleet`
- Dashboard Premium: 1 request
- Fleet Command Center: 1 request  
- Maintenance Dashboard: 1 request
- **Total**: 3+ requests simultáneos al mismo endpoint

**Después**: Sistema de caché compartido con TTL de 5 segundos
- Primer componente: hace request y almacena en caché
- Componentes siguientes: usan datos cacheados
- **Total**: 1 request cada 5 segundos máximo

**Ahorro**: ~70% menos requests, carga instantánea en componentes subsiguientes

### 2. Serialización JSON Optimizada

**Antes**: Lambda simple que no manejaba todos los tipos
```python
json.dumps(record, default=lambda x: None if math.isnan(x) else x)
```

**Después**: Conversión explícita de todos los tipos problemáticos
- numpy.int64 → int
- numpy.float64 → float
- pandas.Timestamp → ISO string
- NaN/Inf → None

---

## 🚀 PRÓXIMAS OPTIMIZACIONES SUGERIDAS

1. **Optimizar endpoint `/alerts`** (actualmente 176ms)
   - Agregar índice en MySQL para columna `timestamp_utc`
   - Implementar caché de 30 segundos

2. **Implementar Service Worker** en frontend
   - Caché offline de assets estáticos
   - Carga instantánea en visitas repetidas

3. **Lazy Loading** de componentes pesados
   - TruckDetail components
   - Chart libraries (recharts)

---

## 📝 NOTAS IMPORTANTES

1. **LaunchD NO está configurado**: Los servicios NO se inician automáticamente al encender la Mac
2. **Debes usar el script manual** cada vez que reinicies el sistema
3. **Los logs se acumulan**: Considera limpiar logs antiguos periódicamente:
   ```bash
   # Mantener solo logs de últimos 7 días
   find logs/ -name "*.log" -mtime +7 -delete
   ```

4. **Frontend puerto dinámico**: Vite puede usar puertos 3000, 3001, 3004, 5173 según disponibilidad
   - El script de inicio detecta el puerto usado
   - Verifica el output del script para saber el puerto exacto

---

## ✅ CHECKLIST DE INICIO DIARIO

- [ ] Ejecutar `bash services/start_with_logs.sh`
- [ ] Verificar que muestre "✅ Backend API respondiendo"
- [ ] Verificar que muestre "✅ Frontend iniciado"
- [ ] Abrir navegador en la URL del frontend mostrada
- [ ] Verificar que el dashboard cargue los datos

**Si algo falla**: Revisar logs en `logs/backend_*.log` y `logs/frontend_*.log`

---

Creado: Diciembre 29, 2025
Última actualización: Diciembre 29, 2025
Versión: 1.0
