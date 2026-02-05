import asyncio
import json
import random

# CONSTANTS

PRODUCT_TAGGING_URL = "https://app.perle.xyz/project/12c9735b-1704-4d1e-bf09-38c6a8c06e52"
MEDICAL_SPECIALTY_URL = "https://app.perle.xyz/project/146dc52a-4894-4073-b2be-6bdaf113a3cc"
LEGAL_CLASSIFICATION_URL = "https://app.perle.xyz/project/15a793d9-0857-49a4-8779-0986ae8cce6a"
AMBIGUOUS_INSTRUCTION_IDENTIFICATION_URL = "https://app.perle.xyz/project/17cba5a0-ce87-4ec0-93d3-11276b8cf9bb"


PRODUCT_DATA = "data/product_tagging.json"
MEDICAL_DATA = "data/medical_specialty.json"
LEGAL_DATA = "data/legal_classification.json"
AMBIGUOUS_DATA = "data/ambiguous_instruction_identification.json"

METAMASK_URL = "chrome-extension://nkbihfbeogaeaoehlefnkodbefgpgknn/home.html"
MM_PASSWORD_INPUT = "xpath=/html/body/div[1]/div/div/div/form/div/div[2]/div/input"
MM_UNLOCK_BTN = "xpath=/html/body/div[1]/div/div/div/form/div/button[1]"
MM_CONFIRM_BTN = "xpath=/html/body/div[1]/div/div/div/div/div/div/div[2]/button[2]"

SUBMIT_BTN = "xpath=/html/body/div/div[1]/div[2]/main/div/div[2]/div[4]/div[3]/button"


def normalize(text: str) -> str:
    return " ".join(text.lower().split())


def load_answers(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


async def safe_goto(page, url, logger):
    try:
        await page.goto(url, timeout=20000)
    except Exception as e:
        if "ERR_ABORTED" in str(e):
            logger.warning("ERR_ABORTED ignored (ADS behavior)")
        else:
            raise
    await asyncio.sleep(2)

# METAMASK UNLOCK

async def unlock_metamask(page, password, logger):
    await safe_goto(page, METAMASK_URL, logger)

    try:
        pwd = page.locator(MM_PASSWORD_INPUT)
        await pwd.wait_for(state="visible", timeout=7000)

        if password:
            await pwd.fill(password)
            await page.locator(MM_UNLOCK_BTN).click(force=True)
        else:
            logger.info("Waiting manual MetaMask unlock")

        await pwd.wait_for(state="detached", timeout=120000)
        logger.info("MetaMask unlocked")

    except Exception:
        logger.info("MetaMask already unlocked")



# QUEST ENTRY (видео ожидание)

async def handle_quest_entry(page, logger):
    container = page.locator("xpath=/html/body/div[3]")
    if await container.count() == 0:
        return

    btn = container.locator("button")
    if await btn.count() == 0:
        return

    # пауза при первом входе в квест
    await asyncio.sleep(2)

    if await btn.first.is_disabled():
        logger.info("Quest entry button is disabled, activating...")

        # клик в центр контейнера
        await page.locator(
            "xpath=/html/body/div[3]/div/div[1]"
        ).click(force=True)

        # ждём до 45 секунд
        for i in range(47):
            if not await btn.first.is_disabled():
                logger.info(f"Quest entry button activated after {i + 1}s")
                break
            await asyncio.sleep(1)
        else:
            logger.warning("Quest entry button stayed disabled after 45s")
            return

        # кликаем 
        await btn.first.click(force=True)
        logger.info("Quest entry button clicked")



# SUBMIT + METAMASK CONFIRM

async def submit_and_confirm(page, context, logger):
    
    #SUBMIT
    submit_btn = page.locator(
        "xpath="
        "/html/body/div/div[1]/div[2]/main/div/div[2]/div[4]/div[3]/button | "
        "/html/body/div/div[1]/div[2]/main/div/div[2]/div[4]/div[3]/div/div/button"
    )

    if await submit_btn.count() > 0:
        btn = submit_btn.first

        await btn.wait_for(state="visible", timeout=10000)

        # ждём пока кнопка станет активной
        for _ in range(30):
            if not await btn.is_disabled():
                break
            await asyncio.sleep(0.5)

        await btn.click(force=True)
        logger.info("Submit button clicked")
    else:
        logger.info("Submit button not found, skipping submit step")

    # Submit Transaction 
    modal = page.locator("xpath=/html/body/div[3]/div")
    await modal.wait_for(state="visible", timeout=20000)

    submit_tx_btn = modal.get_by_role("button", name="Submit Transaction")
    await submit_tx_btn.wait_for(state="visible", timeout=20000)

    # MetaMask popup submit
    async with context.expect_page() as popup:
        await submit_tx_btn.click(force=True)

    mm_page = await popup.value

    confirm_btn = mm_page.locator(
        "xpath=/html/body/div[1]/div/div/div/div/div/div/div[2]/button[2]"
    )

    await confirm_btn.wait_for(state="visible", timeout=20000)

    for _ in range(30):
        if not await confirm_btn.is_disabled():
            break
        await asyncio.sleep(0.5)

    await confirm_btn.click(force=True)
    logger.info("MetaMask confirm clicked")

    # ОЖИДАНИЕ РЕЗУЛЬТАТА
    for _ in range(30):
        if await page.get_by_text("Transaction failed", exact=False).count() > 0:
            logger.warning("Transaction failed detected")
            return "failed"

        if await page.get_by_text("Transaction completed", exact=False).count() > 0:
            logger.info("Transaction completed detected")
            return "completed"

        await asyncio.sleep(1)

    return None



async def wait_result(page):
    await asyncio.sleep(2)
    if await page.get_by_text("Transaction failed", exact=False).count() > 0:
        return "failed"
    if await page.get_by_text("Transaction completed", exact=False).count() > 0:
        return "completed"
    return None


# PRODUCT TAGGING

async def solve_product_task(page, context, logger, data):
    # контейнер текста задания
    text_container = page.locator(
        "xpath=/html/body/div/div[1]/div[2]/main/div/div[2]/div[3]/div/div/div/div[2]/div[2]/div"
    )
    await text_container.wait_for(state="visible", timeout=20000)

    # ищем <mark> внутри текста задания
    mark_count = await text_container.locator("xpath=.//mark").count()

    if mark_count > 0:
        logger.info(f"Answer already selected (<mark> found: {mark_count}), skipping selection")
    else:
        # читаем текст
        full_text = await text_container.inner_text()
        norm_text = normalize(full_text)

        # ищем ответ в json
        answer = next(
            (item["answer"] for item in data if normalize(item["text"]) == norm_text),
            None,
        )

        if not answer:
            raise Exception("Answer not found for product task")

        # гибридное выделение ответа
        await page.evaluate(
            """
            ({ el, answer }) => {
                const text = el.innerText;
                const lowerText = text.toLowerCase();
                const lowerAnswer = answer.toLowerCase();
                const index = lowerText.indexOf(lowerAnswer);
                if (index === -1) return;

                const range = document.createRange();
                let current = 0;

                const walker = document.createTreeWalker(
                    el,
                    NodeFilter.SHOW_TEXT,
                    null,
                    false
                );

                let startNode, endNode, startOffset, endOffset;

                while (walker.nextNode()) {
                    const node = walker.currentNode;
                    const len = node.textContent.length;

                    if (!startNode && current + len >= index) {
                        startNode = node;
                        startOffset = index - current;
                    }

                    if (startNode && current + len >= index + answer.length) {
                        endNode = node;
                        endOffset = index + answer.length - current;
                        break;
                    }

                    current += len;
                }

                if (!startNode || !endNode) return;

                range.setStart(startNode, startOffset);
                range.setEnd(endNode, endOffset);

                const sel = window.getSelection();
                sel.removeAllRanges();
                sel.addRange(range);

                ['mousedown','mousemove','mouseup'].forEach(e =>
                    el.dispatchEvent(new MouseEvent(e, { bubbles: true }))
                );

                document.dispatchEvent(new Event('selectionchange'));
            }
            """,
            {
                "el": await text_container.element_handle(),
                "answer": answer
            },
        )

    # SUBMIT + CONFIRM
    for _ in range(2):
        result = await submit_and_confirm(page, context, logger)
        if result == "completed" or await wait_result(page) == "completed":
            break
    else:
        raise Exception("Transaction failed twice")

    # continue
    await page.locator("xpath=/html/body/div[3]/div/button").click(force=True)

    # проверка результата
    result_box = page.locator(
        "xpath=/html/body/div/div[1]/div[2]/main/div/div[2]/div[4]/div[3]/div/div/div"
    )
    result_text = await result_box.inner_text()

    return "Correct answer" in result_text

# CHOICE

async def solve_choice_task(page, context, logger, data):
    q = page.locator(
        "xpath=/html/body/div/div[1]/div[2]/main/div/div[2]/div[3]/div/div/div/div[2]"
    )
    await q.wait_for(state="visible", timeout=20000)
    question = normalize(await q.inner_text())

    answer = next(
        (i["answer"] for i in data if normalize(i["text"]) == question),
        None,
    )

    if not answer:
        logger.warning("Answer not found")
        return False

    await page.get_by_text(answer, exact=True).click(force=True)

    for _ in range(2):
        result = await submit_and_confirm(page, context, logger)
        if result == "completed" or await wait_result(page) == "completed":
            break
    else:
        raise Exception("Transaction failed twice")

    await page.locator("xpath=/html/body/div[3]/div/button").click(force=True)

    box = page.locator(
        "xpath=/html/body/div/div[1]/div[2]/main/div/div[2]/div[4]/div[3]/div/div/div"
    )
    txt = await box.inner_text()

    return "Correct answer" in txt


# QUEST RUNNER

async def run_quest(page, context, logger, url, data_path, mode):
    await safe_goto(page, url, logger)
    await handle_quest_entry(page, logger)

    data = load_answers(data_path)

    # храним индексы заданий, которые уже пробовали
    processed_tasks = set()

    while True:
        await page.mouse.wheel(0, 2000)

        container = page.locator(
            "xpath=/html/body/div/div[1]/div[2]/main/div/div/div/div[2]/div[1]/div[2]/div/section/div[2]"
        )

        # собираем кнопки Join / Joined
        buttons = container.locator("button")
        total = await buttons.count()

        task_clicked = False

        for idx in range(total):
            # пропускаем уже обработанные задания
            if idx in processed_tasks:
                continue

            btn = buttons.nth(idx)
            text = (await btn.inner_text()).strip()

            if "Join" not in text:
                continue

            logger.info(f"Trying task index {idx}: {text}")
            processed_tasks.add(idx)

            await btn.click(force=True)
            task_clicked = True

            try:
                if mode == "product":
                    ok = await solve_product_task(page, context, logger, data)
                else:
                    ok = await solve_choice_task(page, context, logger, data)

                if ok:
                    logger.info(f"Task {idx} completed successfully")
                else:
                    logger.warning(f"Task {idx} finished but marked incorrect")

            except Exception as e:
                logger.error(f"Task {idx} failed, skipping. Reason: {e}")

            # возвращаемся на страницу квеста
            await safe_goto(page, url, logger)
            break 

        if not task_clicked:
            logger.info("No more unprocessed tasks found in this quest")
            break


# ENTRY

async def run_all_quests(page, context, account, logger):
    # MetaMask
    await unlock_metamask(page, account["mm_password"], logger)

    # главная страница
    await safe_goto(page, "https://app.perle.xyz/", logger)

    # описание квестов
    quests = [
        {
            "name": "Medical Specialty",
            "url": MEDICAL_SPECIALTY_URL,
            "data": MEDICAL_DATA,
            "mode": "choice",
        },
        {
            "name": "Legal Classification",
            "url": LEGAL_CLASSIFICATION_URL,
            "data": LEGAL_DATA,
            "mode": "choice",
        },
        {
            "name": "Ambiguous Instruction Identification",
            "url": AMBIGUOUS_INSTRUCTION_IDENTIFICATION_URL,
            "data": AMBIGUOUS_DATA,
            "mode": "product",
        },
    ]

    # начинаем с Product Tagging
    logger.info("Starting Product Tagging quest")
    await run_quest(
        page,
        context,
        logger,
        PRODUCT_TAGGING_URL,
        PRODUCT_DATA,
        "product",
    )

    # рандом квесты
    random.shuffle(quests)

    # выполняем квест 
    for quest in quests:
        logger.info(f"Starting quest: {quest['name']}")
        try:
            await run_quest(
                page,
                context,
                logger,
                quest["url"],
                quest["data"],
                quest["mode"],
            )
        except Exception as e:
            logger.error(f"Quest {quest['name']} failed: {e}")
            # fail-soft: идём дальше

