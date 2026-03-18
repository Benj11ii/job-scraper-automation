# Buscador de Trabajo Chile

Sistema automatizado de búsqueda laboral con IA local (Ollama).

## Características
- Scraping de ComputTrabajo, Indeed y GetOnBoard
- Evaluación de ofertas con múltiples CVs usando Ollama
- Notificaciones por Telegram con análisis detallado
- Scheduler automático L-V 08:00-23:00 cada 30 minutos
- Búsqueda remota + presencial por ciudad

## Stack
- Python 3.14
- Playwright (scraping)
- Ollama con llama3.2 y qwen3:4b
- SQLite (base de datos local)
- python-telegram-bot

## Configuración
Copiar `.env.example` a `.env` y completar con tus credenciales.
