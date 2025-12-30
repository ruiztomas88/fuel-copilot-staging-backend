# Plan de Acción - Auditoría Backend
**Fecha:** Diciembre 25, 2025

## 🚨 FASE 1: Seguridad (Esta Semana)

### 1.1 Variables de Entorno (HOY)
```bash
# 1. Copiar template
cp env.example .env

# 2. Configurar valores reales
nano .env

# 3. Agregar a .gitignore
echo ".env" >> .gitignore
```

### 1.2 Migrar Credenciales (Esta Semana)
```bash
# Backup primero
tar -czf backend_backup_$(date +%Y%m%d).tar.gz .

# Escanear problemas
python fix_credentials.py --scan .

# Aplicar con backup
python fix_credentials.py --fix --backup .

# Verificar que funciona
python main.py  # Debe leer de .env

# Test manual
curl http://localhost:8000/api/fleet
```

**VALIDACIÓN:** ✅ Ningún archivo tiene passwords hardcodeados

---

## 🛡️ FASE 2: SQL Injection (Próxima Semana)

### 2.1 Instalar Utilidades
```bash
cp sql_safe.py .
cp db_config.py .
```

### 2.2 Migrar Queries (Prioridad Alta)
**Archivos críticos:**
1. `full_diagnostic.py` - Queries dinámicas
2. `user_management.py:335` - UPDATE vulnerable
3. `search_driving_thresholds_data.py` - LIKE injection

**Migración manual (NO automatizar):**
```python
# ANTES
cursor.execute(f"SELECT * FROM {table}")

# DESPUÉS
from sql_safe import safe_count, whitelist_table
table_safe = whitelist_table(table)
count = safe_count(conn, table_safe)
```

**VALIDACIÓN:** ✅ Auditoría de queries con SQLMap o similar

---

## 🔧 FASE 3: Code Quality (Este Mes)

### 3.1 Bare Excepts
```bash
# Escanear
python fix_bare_excepts.py --scan .

# Revisar suggestions
# Aplicar SOLO si tiene sentido
python fix_bare_excepts.py --fix .
```

### 3.2 Cleanup main.py - CON CUIDADO
```bash
# Ver estadísticas primero
python cleanup_main_py.py main.py

# REVISAR MANUALMENTE el código "muerto"
# Buscar referencias a funciones comentadas

# Solo si estás 100% seguro:
python cleanup_main_py.py main.py --clean --backup
```

**⚠️ ADVERTENCIA:** NO borres código que pueda estar referenciado en routers

---

## ⚡ FASE 4: Algorithm Improvements (Backlog)

### 4.1 MPG Adaptativo - Experimental
```python
# Setup en ambiente de pruebas
cp algorithm_improvements.py engines/

# A/B Testing
# - 50% trucks con AdaptiveMPGEngine
# - 50% trucks con engine actual
# - Comparar por 2 semanas

# Métricas:
# - Accuracy vs manual refuels
# - Drift reduction
# - False positive rate
```

### 4.2 Extended Kalman Filter - Research
```python
# NO aplicar en producción aún
# Testing con datos históricos primero

# Comparar vs Kalman actual:
# - Uncertainty bounds
# - Prediction accuracy
# - Computational overhead
```

### 4.3 Theft Detection - Validación
```python
# Probar con datos históricos
# Comparar vs theft_events actual
# Analizar false positives/negatives
```

---

## 📊 Métricas de Éxito

### Seguridad
- [ ] 0 credenciales hardcodeadas
- [ ] 100% queries parametrizados
- [ ] .env configurado en todos los ambientes

### Code Quality
- [ ] 0 bare except clauses
- [ ] main.py < 4,000 líneas
- [ ] Coverage > 60%

### Algoritmos
- [ ] MPG accuracy +5% vs baseline
- [ ] Theft false positives < 2%
- [ ] EKF uncertainty bounds validados

---

## ⏱️ Timeline

| Fase | Duración | Fecha Objetivo |
|------|----------|----------------|
| Fase 1: Seguridad | 3 días | Dic 28 |
| Fase 2: SQL Injection | 5 días | Ene 3 |
| Fase 3: Code Quality | 10 días | Ene 15 |
| Fase 4: Algorithms | 4 semanas | Feb 15 |

---

## 🚫 NO Hacer

1. **NO aplicar todos los scripts a la vez** - Ir de uno en uno
2. **NO borrar código sin revisar referencias** - Especialmente en main.py
3. **NO aplicar algorithm improvements en prod sin testing** - Pueden degradar accuracy
4. **NO commitear .env** - Agregarlo a .gitignore
5. **NO aplicar fixes sin backup** - Siempre usar `--backup`

---

## ✅ Checklist Rápido

**Hoy:**
- [ ] Crear .env desde template
- [ ] Escanear credenciales: `python fix_credentials.py --scan .`
- [ ] Backup: `tar -czf backup.tar.gz .`

**Esta Semana:**
- [ ] Aplicar fix_credentials con backup
- [ ] Verificar que backend funciona con .env
- [ ] Commitear cambios (sin .env)

**Próxima Semana:**
- [ ] Copiar sql_safe.py y db_config.py
- [ ] Migrar queries críticas
- [ ] Testing de SQL injection

**Este Mes:**
- [ ] Fix bare excepts
- [ ] Revisar main.py cleanup
- [ ] Code review completo

---

## 📞 Soporte

Si algo falla:
1. Restaurar desde backup: `tar -xzf backup.tar.gz`
2. Revisar logs: `tail -f backend_server.log`
3. Verificar .env tiene todos los valores necesarios
4. Rollback git: `git checkout -- <archivo>`
