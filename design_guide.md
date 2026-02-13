## 1 & 2. Comprehensive UI Breakdown

### Overall Canvas & Layout Strategy

* **Background:** Solid white.
* **Main Container:** A large rectangular window with a thin black border.
* **Layout Structure:** The UI is divided into three main horizontal zones: Header, Top Statistics Row, and the Main Content Area. The Main Content Area is further divided into a wider Left Column (for statuses and logs) and a narrower Right Sidebar (for person details).

### Zone 1: The Header (Top Row)

* **Positioning:** Spans the full width of the top, elements are vertically centered.
* **App Title (Left):** "Wedding FaceForward" in a large, bold, black sans-serif font.
* **Controls (Right):** A horizontally stacked group of three interactive elements, right-aligned:
  * **START Button:** Pill-shaped (fully rounded corners), bright green background, white bold text saying "START".
  * **Theme Toggle:** A circle with a black outline containing a yellow multi-pointed sun icon. (Note: The mockup has a text callout "dark/light mode" with a black arrow pointing down to it, which acts as an annotation rather than a permanent UI element).
  * **OPEN FOLDER Button:** Pill-shaped, light grey background, black bold text saying "OPEN FOLDER".
* **Spacing:** Even, moderate gaps between these three controls.

### Zone 2: Top Statistics Row

* **Positioning:** Immediately below the header, spanning the full width. It operates as a horizontal flex-row or grid of five equally sized, rectangular cards.
* **Cards 1–4 (Standard Stats):**
  * **Design:** Rectangles with slightly rounded corners. Background is a light peach/beige color. No borders.
  * **Content:** Centered, black, bold, uppercase text.
  * **Labels:** "TOTAL PHOTOS", "TOTAL FACES", "NO OF PERSONS", "ENROLLED".
* **Card 5 (Status Highlight):**
  * **Design:** Same shape and size as the others, but with a slightly darker, more yellow/beige background.
  * **Content:** Centered, black, bold text spanning two lines.
  * **Label:** "Cloud and Local\nMatch ?".

### Zone 3: Main Content Area (Bottom Section)
This section is split into two distinct layout columns.

#### Left Column (Status & Logs)

* **Status Cards Row (Middle Left):**
  * **Positioning:** Below the Top Stats row, aligned to the left. Three cards displayed horizontally.
  * **Design:** White rectangles with prominent, thick black borders and rounded corners.
  * **Content:** Centered, black, bold, uppercase text.
  * **Labels:** "PROCESSING", "CLOUD SYNC", "STUCK PHOTOS IN PROCESSING".
* **Activity Log (Bottom Left):**
  * **Positioning:** Below the Status Cards, filling the remaining vertical and horizontal space of the left column.
  * **Outer Container:** A large rectangle with a dark grey background, thick black border, and rounded corners.
  * **Title:** The text "ACTIVITY LOG" is placed at the top-left inside this grey container (bold, black, sans-serif).
  * **Inner Screen:** A massive, solid black rectangle with rounded corners that fills the majority of the grey container, leaving a uniform dark grey padding around it. This is intended for the console/terminal output.

#### Right Column (Sidebar List)

* **Positioning:** Spans vertically from just below the Top Statistics Row all the way down to align with the bottom of the Activity Log. It sits to the right of the Status Cards and Activity Log.
* **Outer Container:** A tall white rectangle with a thick black border and rounded corners.
* **Inner Content (List Items):**
  * A vertically stacked list of 14 identical UI components.
  * **Item Design:** Wide, pill-shaped outlines (thick black borders, white inside, fully rounded ends).
  * **Spacing:** Tight vertical gaps between each pill.
  * **Text Layout:** Each pill contains left-aligned text (e.g., "person_1") and right-aligned numerical data (e.g., "34"). The text is standard, unbolded black sans-serif.

---

## 3. AI Generation Prompt
Copy and paste the text block below into an AI code generator (like Claude, ChatGPT, or v0) to have it build this UI.

> **System Prompt: Act as an expert UI/UX developer.**
> Your task is to build a responsive desktop-style dashboard layout based on the exact specifications below. Use a modern sans-serif font for all text.
> 
> **Global Layout Structure:**
> Create a main application window with a white background and a thin black border. Add standard padding inside the main window. Use CSS Grid or Flexbox to divide the screen into three primary vertical sections: a Header, a Stats Row, and a Main Content split (Left and Right).
> 
> **1. Header (Top Row):**
> 
> * Create a flex container with justify-content: space-between and align-items: center.
> * **Left side:** An h1 title reading "Wedding FaceForward" in bold, black text.
> * **Right side:** A flex container with three items spaced evenly:
>   * A "START" button (pill-shaped, bright green background, white bold text, no border).
>   * A Theme Toggle button (circular with a black outline, white background, containing a yellow sun icon).
>   * An "OPEN FOLDER" button (pill-shaped, light grey background, black bold text, no border).
> 
> **2. Statistics Row (Directly below Header):**
> 
> * Create a grid or flex row with 5 equal-width rectangular cards. Add a small gap between them. Add border-radius for slightly rounded corners.
> * Cards 1 to 4 should have a light peach/beige background (#FCEFCD or similar). Texts: "TOTAL PHOTOS", "TOTAL FACES", "NO OF PERSONS", "ENROLLED".
> * Card 5 should have a slightly darker yellow/beige background (#F6E9B2 or similar). Text: "Cloud and Local Match ?".
> * All text in these cards should be black, bold, perfectly centered, and use uppercase where specified.
> 
> **3. Main Content Area (Below Stats Row):**
> 
> * Create a flex container or CSS grid divided into two columns: a Left Column (taking up about 70% width) and a Right Sidebar Column (taking up about 30% width). Add a gap between the columns.
> 
> **3A. Left Column (Statuses and Logs):**
> 
> * **Top Row (Statuses):** A horizontal flex row of 3 equal-width cards. They must have a white background, a thick black border (e.g., border: 3px solid black), and rounded corners. Texts: "PROCESSING", "CLOUD SYNC", "STUCK PHOTOS IN PROCESSING". Text should be centered, black, and bold.
> * **Bottom Area (Activity Log):** A large container taking up all remaining vertical space in this column. It should have a dark grey background (#7A7A7A), a thick black border, and rounded corners. Inside, add top-left aligned bold black text: "ACTIVITY LOG". Below that text, fill the rest of the container with a solid black rectangle with rounded corners to represent a terminal window. Add padding so the dark grey background shows as a border around the black screen.
> 
> **3B. Right Sidebar Column (Person List):**
> 
> * A tall container spanning the height of the left column's elements. It must have a white background, a thick black border, and rounded corners. Add padding inside.
> * Inside, create a vertically scrolling list of 14 items.
> * **List Item styling:** Each item is a pill shape (fully rounded ends, e.g., border-radius: 50px), with a thick black border and white background. Use flexbox inside the pill with justify-content: space-between to place text on the left (e.g., "person_1", "person_2", up to 14) and a number on the right (e.g., "34").