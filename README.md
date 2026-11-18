# Odoo 19 Sales Automation & Telegram Integration

A Telegram-based sales automation system integrating Odoo 19, n8n, Ollama, and PostgreSQL.

Customers can browse products, check prices and stock, manage shopping carts, and submit orders through Telegram. The system automatically creates sales quotations in Odoo.

## Tech Stack

- **Odoo 19** – ERP & Sales Management
- **n8n** – Workflow Automation
- **Ollama (Qwen2.5:3B)** – Local LLM & Intent Classification
- **Telegram Bot API** – Customer Interaction
- **PostgreSQL** – Shopping Cart & Workflow Data
- **Python / REST API** – Odoo Integration
- **Docker** – Containerization

## Key Features

- Telegram chatbot integration
- AI-powered customer message processing
- Product browsing and searching by name or code
- Product price and stock information
- Multi-product shopping cart management
- Add, update, and remove cart items
- Delivery address collection
- Customer registration in Odoo
- Automatic sales quotation creation in Odoo
- Order confirmation and cancellation

## Workflow Architecture

Telegram Customer → Telegram Bot → n8n → Ollama (LLM) → Intent Detection → Workflow Routing → Odoo 19 & PostgreSQL → Sales Quotation → Telegram Response

## Order Workflow

1. Customer interacts with the Telegram Bot.
2. Ollama identifies customer intent.
3. Customer searches or browses products.
4. Customer adds products to the shopping cart.
5. Customer updates quantities or removes items.
6. Customer provides a delivery address.
7. n8n sends order information to Odoo.
8. Odoo automatically creates a sales quotation.
9. Customer can confirm or cancel the order.

## Author

Kay Khaing Oo | ERP Integration & Workflow Automation