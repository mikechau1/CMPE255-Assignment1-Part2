import { expect, test, type Page } from "@playwright/test";

/**
 * These run against a seeded database and a production build. Each test makes
 * its own task with a unique title where it needs to mutate, so the specs do
 * not depend on each other's leftovers or on exact seed counts.
 *
 * One behaviour worth stating up front, because several tests rest on it:
 * completing a task removes it from the open lists (All, Today, a project) and
 * moves it to Completed. The undo toast is the way back.
 */

const unique = (label: string) => `${label} ${Date.now()}-${Math.floor(Math.random() * 1000)}`;

/** The quick-add box, which is the first control on every editable view. */
function quickAdd(page: Page) {
  return page.getByRole("textbox", { name: "Add a task" });
}

function taskRow(page: Page, title: string) {
  return page.getByTestId("task-row").filter({ hasText: title });
}

/** The title button inside a row — `exact` keeps it apart from "Reorder X" etc. */
function taskTitleButton(page: Page, title: string) {
  return taskRow(page, title).getByRole("button", { name: title, exact: true });
}

async function addTask(page: Page, text: string) {
  await quickAdd(page).fill(text);
  await quickAdd(page).press("Enter");
}

test.describe("views and navigation", () => {
  test("today shows seeded work and the sidebar navigates", async ({ page }) => {
    await page.goto("/today");

    await expect(page.getByRole("heading", { name: "Today", level: 1 })).toBeVisible();
    await expect(taskRow(page, "Team standup")).toBeVisible();

    await page.getByRole("link", { name: /^Upcoming/ }).first().click();
    await expect(page.getByRole("heading", { name: "Upcoming", level: 1 })).toBeVisible();

    await page.getByRole("link", { name: /^Stats/ }).first().click();
    await expect(page.getByRole("heading", { name: "Stats", level: 1 })).toBeVisible();
    await expect(page.getByText("Tasks completed, last 30 days")).toBeVisible();
  });

  test("today includes overdue tasks, not just today's", async ({ page }) => {
    await page.goto("/today");
    // Seeded three days in the past.
    await expect(taskRow(page, "Renew parking permit")).toBeVisible();
  });

  test("the root path redirects to today", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/today$/);
  });
});

test.describe("quick add", () => {
  test("parses date, time, priority, project and tag from one line", async ({ page }) => {
    await page.goto("/all");
    const title = unique("Pay rent");

    await quickAdd(page).fill(`${title} tomorrow 5pm #Home @bills !p1`);

    // The preview shows what will be created before anything is committed.
    const preview = page.getByTestId("quick-add-preview");
    await expect(preview).toContainText("Tomorrow 5:00 PM");
    await expect(preview).toContainText("Urgent");
    await expect(preview).toContainText("Home");
    await expect(preview).toContainText("bills");

    await quickAdd(page).press("Enter");

    const row = taskRow(page, title);
    await expect(row).toBeVisible();
    // The tokens are stripped from the stored title.
    await expect(row).not.toContainText("#Home");
    await expect(row).not.toContainText("!p1");
    await expect(row).toContainText("Tomorrow 5:00 PM");
    await expect(row).toContainText("Urgent");
    await expect(row).toContainText("bills");

    // The project named in the text was created and is now in the sidebar.
    await expect(page.getByRole("link", { name: /^Home/ }).first()).toBeVisible();
  });

  test("leaves a plain title alone", async ({ page }) => {
    await page.goto("/all");
    const title = unique("Buy 5 apples");

    await addTask(page, title);
    await expect(taskRow(page, title)).toBeVisible();
    await expect(taskRow(page, title)).not.toContainText("PM");
  });
});

test.describe("completing and undo", () => {
  test("completing moves a task to Completed, and undo brings it back", async ({ page }) => {
    await page.goto("/all");
    const title = unique("Restore me");
    await addTask(page, title);

    await taskRow(page, title).getByRole("checkbox").click();

    await expect(page.getByText("Task completed")).toBeVisible();
    await expect(taskRow(page, title)).toHaveCount(0);

    await page.goto("/completed");
    await expect(taskRow(page, title)).toHaveAttribute("data-completed", "true");

    // Reopening from the Completed view sends it back to the open list.
    await taskRow(page, title).getByRole("checkbox").click();
    await expect(taskRow(page, title)).toHaveCount(0);

    await page.goto("/all");
    await expect(taskRow(page, title)).toBeVisible();
  });

  test("the undo toast restores a completed task in place", async ({ page }) => {
    await page.goto("/all");
    const title = unique("Toast undo");
    await addTask(page, title);

    await taskRow(page, title).getByRole("checkbox").click();
    await expect(taskRow(page, title)).toHaveCount(0);

    await page.getByRole("button", { name: "Undo", exact: true }).click();
    await expect(taskRow(page, title)).toBeVisible();
    await expect(taskRow(page, title)).toHaveAttribute("data-completed", "false");
  });

  test("deleting a task is undoable", async ({ page }) => {
    await page.goto("/all");
    const title = unique("Delete me");
    await addTask(page, title);

    await taskRow(page, title).getByRole("button", { name: `More actions for ${title}` }).click();
    await page.getByRole("menuitem", { name: "Delete" }).click();

    await expect(taskRow(page, title)).toHaveCount(0);
    await page.getByRole("button", { name: "Undo", exact: true }).click();
    await expect(taskRow(page, title)).toBeVisible();
  });

  test("a deleted task waits in the trash and can be restored there", async ({ page }) => {
    await page.goto("/all");
    const title = unique("Trash me");
    await addTask(page, title);

    await taskRow(page, title).getByRole("button", { name: `More actions for ${title}` }).click();
    await page.getByRole("menuitem", { name: "Delete" }).click();
    await expect(taskRow(page, title)).toHaveCount(0);

    await page.goto("/trash");
    const trashed = page.getByRole("listitem").filter({ hasText: title });
    await expect(trashed).toBeVisible();

    await trashed.getByRole("button", { name: "Restore" }).click();
    await page.goto("/all");
    await expect(taskRow(page, title)).toBeVisible();
  });
});

test.describe("recurring tasks", () => {
  test("completing a repeating task schedules the next occurrence", async ({ page }) => {
    await page.goto("/all");
    const title = unique("Water the fern");

    await addTask(page, `${title} every day`);
    const row = taskRow(page, title);
    await expect(row).toContainText("Daily");
    await expect(row).toContainText("Today");

    await row.getByRole("checkbox").click();
    await expect(page.getByText("next one scheduled")).toBeVisible();

    // The completed instance moved to Completed; its replacement is open and
    // due a day later.
    await page.reload();
    const next = taskRow(page, title);
    await expect(next).toHaveCount(1);
    await expect(next).toHaveAttribute("data-completed", "false");
    await expect(next).toContainText("Tomorrow");
    await expect(next).toContainText("Daily");
  });
});

test.describe("search and filter", () => {
  test("search narrows the list and clears with Escape", async ({ page }) => {
    await page.goto("/all");
    const title = unique("Zymurgy notes");
    await addTask(page, title);

    const search = page.getByRole("searchbox", { name: "Search tasks" });
    await search.fill("Zymurgy");

    await expect(taskRow(page, title)).toBeVisible();
    await expect(taskRow(page, "Team standup")).toHaveCount(0);

    await search.press("Escape");
    await expect(taskRow(page, "Team standup")).toBeVisible();
  });

  test("filtering by priority hides everything else", async ({ page }) => {
    await page.goto("/all");
    const urgent = unique("Critical fix");
    await addTask(page, `${urgent} !p1`);

    await page.getByRole("button", { name: "Filter" }).click();
    await page.getByRole("menuitem", { name: "Urgent" }).click();
    await page.keyboard.press("Escape");

    await expect(taskRow(page, urgent)).toBeVisible();
    await expect(taskRow(page, "Water the plants")).toHaveCount(0);
  });
});

test.describe("keyboard", () => {
  test("n focuses quick add and the command palette opens with the keyboard", async ({ page }) => {
    await page.goto("/all");

    await page.locator("body").press("n");
    await expect(quickAdd(page)).toBeFocused();
    await quickAdd(page).press("Escape");

    await page.locator("body").press("Control+k");
    await expect(page.getByPlaceholder("Search tasks or type a command")).toBeVisible();
    await page.keyboard.press("Escape");

    await page.locator("body").press("?");
    await expect(page.getByRole("heading", { name: "Keyboard shortcuts" })).toBeVisible();
  });

  test("j and Space complete a task without a mouse", async ({ page }) => {
    await page.goto("/all");
    const title = unique("Keyboard task");
    await addTask(page, title);
    await expect(taskRow(page, title)).toBeVisible();
    // Quick add refocuses itself after a submit so several tasks can be typed
    // in a row; step out of it or the single-key shortcuts stay suppressed.
    await quickAdd(page).blur();

    // One press of "j" puts the cursor on the first row; complete that one.
    // (Positions are per project, so a new task is not reliably last in All.)
    const firstRow = page.getByTestId("task-row").first();
    const firstId = await firstRow.getAttribute("data-task-id");
    const firstTitle = (await firstRow.innerText()).split(String.fromCharCode(10))[0]!;

    await page.keyboard.press("j");
    await expect(firstRow).toHaveClass(/ring-accent/);

    await page.keyboard.press(" ");
    await expect(page.locator(`[data-task-id="${firstId}"]`)).toHaveCount(0);

    await page.goto("/completed");
    await expect(taskRow(page, firstTitle)).toBeVisible();
  });
});

test.describe("reordering", () => {
  test("a keyboard drag persists across a reload", async ({ page }) => {
    await page.goto("/all");

    const rows = page.getByTestId("task-row");
    const firstId = await rows.first().getAttribute("data-task-id");
    expect(firstId).toBeTruthy();

    // dnd-kit's keyboard sensor: focus the handle, Space to lift, arrow to
    // move, Space to drop. The short pauses let the lift and move animations
    // settle — sent back to back, the sensor drops the ArrowDown.
    await rows.first().getByRole("button", { name: /^Reorder/ }).focus();
    await page.keyboard.press(" ");
    await page.waitForTimeout(250);
    await page.keyboard.press("ArrowDown");
    await page.waitForTimeout(250);
    await page.keyboard.press(" ");

    await expect(rows.nth(1)).toHaveAttribute("data-task-id", firstId!);

    await page.reload();
    await expect(page.getByTestId("task-row").nth(1)).toHaveAttribute("data-task-id", firstId!);
  });
});

test.describe("task details", () => {
  test("the detail panel edits fields in place", async ({ page }) => {
    await page.goto("/all");
    const title = unique("Detailed task");
    await addTask(page, title);

    await taskTitleButton(page, title).click();
    await expect(page.getByRole("dialog")).toBeVisible();

    await page.getByRole("textbox", { name: "Task title" }).fill(`${title} edited`);
    await page.getByRole("textbox", { name: "Notes" }).click();
    await page.getByRole("textbox", { name: "Notes" }).fill("Some context");
    await page.getByRole("button", { name: "High", exact: true }).click();

    await page.getByRole("button", { name: "Close details" }).click();

    const row = taskRow(page, `${title} edited`);
    await expect(row).toBeVisible();
    await expect(row).toContainText("High");
  });

  test("subtasks add and complete", async ({ page }) => {
    await page.goto("/all");
    const title = unique("Parent task");
    await addTask(page, title);

    await taskTitleButton(page, title).click();
    const subtaskInput = page.getByRole("textbox", { name: "Add a subtask" });
    await subtaskInput.fill("First step");
    await subtaskInput.press("Enter");

    await expect(page.getByRole("checkbox", { name: "Complete First step" })).toBeVisible();
    await page.getByRole("checkbox", { name: "Complete First step" }).click();

    await page.getByRole("button", { name: "Close details" }).click();
    await expect(taskRow(page, title)).toContainText("1/1");
  });
});

test.describe("theme and responsiveness", () => {
  test("dark mode toggles and sticks", async ({ page }) => {
    await page.goto("/today");

    await page.getByRole("button", { name: /Switch to (dark|light) mode/ }).click();
    await expect(page.locator("html")).toHaveClass(/dark/);

    await page.reload();
    await expect(page.locator("html")).toHaveClass(/dark/);
  });

  test("the mobile layout has no horizontal overflow", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 780 });
    await page.goto("/today");

    await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();

    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(1);
  });
});
