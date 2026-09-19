# AI Kassir — алоҳида Telegram кассир боти (TEST)

Telegram: https://t.me/A1Kassir_bot

**GitHub:** мазкур репозиторий код базаси. **Render test service:** https://dashboard.render.com/web/srv-dandr0oae00c73eekdn0 · https://ai-kassir-test.onrender.com/health

## Жорий ҳолат

Render веб-хизмати бепул режада яратилган; дастур тестлардан ўтган. У ҳозир **setup_required** режимида: шахсий Telegram бот токени, WEBHOOK_SECRET, ADMIN_TELEGRAM_ID ва **алоҳида, доимий** DATABASE_URL созланмагунча Telegram операцияларини қабул қилмайди (HTTP 503). Бу молиявий маълумотлар вақтинчалик хотирага ёзилиб йўқолмаслиги учун.

Render аккаунтида бир бепул Postgres мавжуд бўлгани сабаб иккинчи бепул база очиш рад этилди. **Ҳисобчи AI базасига тегманг ва уни қайта ишлатманг**. Янги Render Postgres базаси учун нарх режасини аввал тасдиқланг ёки алоҳида ташқи доимий PostgreSQL манзилини уланг.

**Эски Hisobchi AI боти, Render хизмати, токени ва маълумотлар базаси ўзгармайди.**

## Хавфсиз созлаш

1. Репозиторийни GitHub Settings → General → Danger Zone → Change repository visibility → **Private** қилинг. У ҳозир Public.
2. Янги Telegram бот учун @BotFather берган токенни (эски ботники эмас) Render **AI Kassir test → Environment** қисмида `BOT_TOKEN` номи билан киритинг. Токенни чатга ёки GitHubга ёзманг.
3. Шу ерда `ADMIN_TELEGRAM_ID` (янги ботни бошқарадиган Telegram ҳисобингизнинг ID рақами), `WEBHOOK_SECRET` (тасодифий, камида 32 байт, URL-safe), ихтиёрий `OPENAI_API_KEY` (AI ва овоз учун), ва янги мустақил Postgres **internal connection URL** ни `DATABASE_URL`га киритинг. Реал токен/паролни фақат Render секретлар қисмида сақланг.
4. Deploy live бўлиб, `/health` → `{"status":"ok"}` деб қайтаргач, янги Telegram токени билан `setWebhook`ни `https://ai-kassir-test.onrender.com/webhook/<WEBHOOK_SECRET>` манзилига созланг. URLдаги секретни оммага кўрсатманг.
5. Ботнинг шахсий чатида /start, /id, 500 USD кирим, 1 000 000 UZS аванс чиқим, /balance ва /todayни текширинг.

> Мазкур дастур **ишлаб чиқариш ёки ҳақиқий нақд пул ҳисобини юритиш учун ҳали тайёр эмас**: бошланғич касса қолдиғи, кун ёпилиши, бекор қилиш аудити, захира нусхаси, чек/ҳужжат ва бир овозда кўп операция функциялари ҳали йўқ. /balance — бошланғич қолдиқсиз фақат қайд этилган ҳаракатлар йиғиндиси.

## Дастлабки командалар

/start, /help, /id, /balance, /today, /month, /allow <TELEGRAM_ID> (фақат админ).

Кассир бир дона аниқ операцияни овоз ёки матн билан юборади, бот унинг суммаси/валютаси/категориясини тасдиқлатгачгина мустақил базага ёзади.
