# Registro de implementacion - LegalFlow Workflow

Fecha: 2026-06-04

## Objetivo

Implementar un flujo por etapas donde la salida de un agente active el siguiente, con soporte para:

- modo local (sin API)
- modo SDK real (Cursor SDK)
- caso de ejemplo reproducible

## Cambios aplicados

Archivo principal actualizado: `agente.py`

Se implemento:

1. Pipeline por etapas:
   - Ingesta
   - Extraccion de clausulas
   - Analisis de riesgos
   - Resumen final
2. Encadenamiento via contexto compartido (`contexto`) entre etapas.
3. Modo `local` para pruebas sin credenciales.
4. Modo `sdk` con `cursor_sdk` (`Agent.prompt`) por cada etapa.
5. Flag `--demo` con contrato de ejemplo.
6. Manejo de errores para:
   - SDK no instalado
   - `CURSOR_API_KEY` faltante
   - errores del runtime del agente
   - salida no JSON
7. Ajuste de modelo:
   - default en CLI: `composer-2.5`
   - fallback interno: si llega `auto`, se usa `composer-2.5`

## Problemas encontrados y resolucion

1. Error: `Invalid User API Key`
   - Causa: variable con placeholder o key invalida.
   - Resolucion: usar una key real desde Cursor Dashboard Integrations.

2. Error: `Cannot use this model: auto`
   - Causa: la cuenta/runtime no acepta `auto` en ese contexto.
   - Resolucion: cambiar default/fallback a `composer-2.5`.

## Comandos de ejecucion

Activar entorno:

```bash
cd "/Users/teopalatini/Documents/legalflow-agent"
source venv/bin/activate
```

Demo local:

```bash
python agente.py --modo local --demo
```

Demo SDK:

```bash
export CURSOR_API_KEY="cursor_...tu_key_real..."
python agente.py --modo sdk --demo
```

Forzar modelo especifico:

```bash
python agente.py --modo sdk --model gpt-5.5 --demo
```

## Estado actual

- Workflow implementado y funcional en modo local.
- Integracion SDK lista.
- API key validada por el usuario.
- Error de modelo `auto` corregido en codigo.
- Listo para corrida final en modo SDK y comparacion de salidas.
