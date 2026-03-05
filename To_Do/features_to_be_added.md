# 🚀 Wedding Face Forward - Future Roadmap

This document outlines planned and potential features for the **Wedding Face Forward** ecosystem, categorized by priority and impact.

---

## 🔴 Very Much Needed (High Priority)

*Features that solve immediate pain points or complete the core administrative loop.*

- [x] **Admin Cluster Merge UI**: A side-by-side visual interface in the PySide dashboard to merge person clusters (e.g., merging `Person_001` and `Person_005` if the AI split them).
- [x] **Settings Configuration GUI**: A dedicated tab in the Desktop app to edit `.env` variables (Thresholds, Drive IDs, Paths) without touching text files.
- [x] **Process Health Monitoring**: Real-time graphs for CPU/GPU utilization, processing speed (Photos/Hour), and queue wait times.
- [x] **Self-Healing Database**: Automatic detection and resolution of "stuck" photos or database locks with one-click repair.
- [x] **Auth Persistence**: Improved Google Drive token management to handle refreshing without requiring manual terminal commands.

---

## 🟡 Just a Good Addition (Medium Priority)

*Features that significantly improve the user experience and professional feel.*

- [ ] **QR Code Generator**: A built-in tool to generate and export branded QR codes for tables/reception so guests can easily find the portal.
- [ ] **Live Event Slideshow**: A "Projector Mode" web route that displays a cinematic, auto-updating slideshow of processed photos for the reception screen.
- [x] **WhatsApp Delivery Tracker**: Real-time status indicators (Queued, Sent, Delivered, Read) for each guest's gallery link.
- [x] **VIP Pinning**: Ability to mark specific clusters (The Bride, The Groom, Parents) to always appear at the top of the admin list.
- [ ] **Enhanced Thumbnails**: Improved face-aware cropping for thumbnails using higher-resolution crops.

---

## 🟢 Completely Optional (Low Priority)

*Features that add "Wow" factor but aren't strictly necessary for the core pipeline.*

- [ ] **"Find My Friends" Discovery**: Section in the guest portal showing "Commonly seen with you" to help guests find family/friends.
- [ ] **Digital Guestbook**: Allow guests to leave a short text message or "Virtual Wish" during the selfie enrollment process.
- [ ] **Request Gallery Zip**: A button for guests to request a structured ZIP of their high-res photos, processed in the background and delivered via WhatsApp.
- [ ] **Dynamic Theme Engine**: Support for different wedding themes (Silver, Gold, Floral, Dark Mode) in the guest portal.
- [ ] **Multi-User Admin**: Basic login protection for the admin dashboard if accessed over a local network.

---

## ⚪ Just In Case (Experimental/Future)

*Edge cases or highly ambitious features for a full enterprise product.*

- [ ] **AI Auto-Enhance**: Basic color correction, white balance, and noise reduction for low-light reception photos.
- [ ] **Event Highlight Detection**: AI training/prompting to identify critical moments like "The Kiss," "Cake Cutting," or "Ring Exchange."
- [ ] **Backup Delivery Channels**: Automatic fallback to Email or Telegram if a WhatsApp number is invalid or the worker is blocked.
- [ ] **Multi-Camera Ingest**: Concurrent monitoring of multiple `Incoming` folders (e.g., Primary Photographer, Secondary, and Photobooth).
- [ ] **Social Media Export**: One-click sharing of matched photos directly to Instagram Stories or Facebook from the guest portal.
- [ ] **Local Storage Mode**: A completely offline mode for venues with zero internet, storing everything on a local server/Wi-Fi hotspot.

---

*Last Updated: 2026-03-04*
