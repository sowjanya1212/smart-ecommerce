# Demo walkthrough & screenshot checklist

Use this script to verify the system and to capture the screenshots/video for the deliverable
(save images to `docs/screenshots/`). Run `make seed` first.

| # | Action | Expect | Screenshot name |
|---|---|---|---|
| 1 | Open http://localhost:8000 | Product grid, filters, search | `01-storefront.png` |
| 2 | Filter by category, price range, sort "Most popular" | Grid updates | `02-filters.png` |
| 3 | Sign up with a new email | Welcome toast + bell badge = 1 | `03-signup.png` |
| 4 | Add 2 products to the cart | Cart badge updates; open it in a 2nd tab → updates live | `04-cart.png` |
| 5 | Checkout with an address → "Pay successfully" (mock) or Stripe test card | Order → *processing / paid*; toast "Payment received" | `05-checkout.png` |
| 6 | Checkout again → "Simulate failure" | Red toast "Payment failed"; order shows **Pay now** | `06-payment-failed.png` |
| 7 | Open 📦 Orders and 🔔 Notifications | History + notification list | `07-orders.png`, `08-notifications.png` |
| 8 | Keep the customer tab open. In http://localhost:8001/admin/ (admin) → Orders → select the order → *Mark as shipped* | **Customer tab shows a live toast "order is now shipped"** (WebSocket) and an email is printed in the Django console | `09-realtime-shipping.png` |
| 9 | http://localhost:8001/dashboard/ | KPIs, revenue trend, top products, status doughnut, low-stock list | `10-dashboard.png` |
| 10 | Click CSV and PDF export buttons | Files download | `11-exports.png` |
| 11 | Admin → Users → add a *staff* user; log in as staff | Staff sees Products/Orders only, no Users | `12-rbac.png` |
| 12 | Admin → Products → add product with images | Image appears in storefront | `13-product-upload.png` |

**Video tip:** record steps 3–9 in one take (≈ 2 min) with the storefront and Django admin side by side.
