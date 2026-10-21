/* WebUntis Stundenplan - ein Zusatzmodul für Dynaframe's Magic Mirror.
 * Nachbau von MMM-Webuntis (HeikoGr, MIT). fetch.py liefert die nächsten
 * Schultage, Prüfungen, Hausaufgaben und Mitteilungen; hier wird gezeichnet.
 * Nach Schulschluss springt der Stundenplan von selbst auf den nächsten Tag. */
(function () {
  "use strict";
  const { esc, t } = window.MagicFrame.helpers;
  const TEXT = {
    exams: { de: "Prüfungen", en: "Exams", es: "Exámenes" },
    homework: { de: "Hausaufgaben", en: "Homework", es: "Deberes" },
    messages: { de: "Mitteilungen", en: "Messages", es: "Avisos" },
    cancelled: { de: "entfällt", en: "cancelled", es: "cancelada" },
    added: { de: "zusätzlich", en: "extra", es: "adicional" },
    instead: { de: "statt", en: "instead of", es: "en lugar de" },
    due: { de: "bis", en: "due", es: "para" },
    noLessons: { de: "Keine Stunden in den nächsten drei Wochen.", en: "No lessons in the next three weeks.", es: "No hay clases en las próximas tres semanas." },
    holiday: { de: "{name} bis {end}", en: "{name} until {end}", es: "{name} hasta el {end}" },
    holidaySoon: { de: "Ab {start}: {name}", en: "From {start}: {name}", es: "Desde el {start}: {name}" },
    holidays: { de: "Ferien", en: "Holidays", es: "Vacaciones" },
    partly: { de: "{what} konnte WebUntis gerade nicht liefern.", en: "WebUntis could not deliver {what} right now.", es: "WebUntis no pudo enviar {what} ahora." },
    nothing: { de: "Nichts Neues.", en: "Nothing new.", es: "Nada nuevo." },
  };

  const pad = (n) => String(n).padStart(2, "0");
  const todayIso = () => { const d = new Date(); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; };
  const nowHm = () => { const d = new Date(); return `${pad(d.getHours())}:${pad(d.getMinutes())}`; };
  const epochOf = (iso) => new Date(`${iso}T12:00:00`).getTime() / 1000;
  const shortDate = (iso, h) => new Date(`${iso}T12:00:00`).toLocaleDateString(h.locale(), { day: "numeric", month: "numeric" });

  // "Heute, 20.10.", "Freitag, 23.10." und weiter weg "Fr., 30.10."; nach "bis" klein: "bis morgen"
  function dayLabel(iso, h, lower = false) {
    let name = h.dayName(epochOf(iso), true);
    if (/\d/.test(name)) name = new Date(`${iso}T12:00:00`).toLocaleDateString(h.locale(), { weekday: "short" });
    const relative = Math.abs(Math.round((epochOf(iso) - epochOf(todayIso())) / 86400)) <= 1;
    if (lower && relative) name = name.toLowerCase();
    return `${name}, ${shortDate(iso, h)}`;
  }

  // 12-Stunden-Uhr, wenn die Szene so eingestellt ist
  function clock(hm, ctx) {
    if (!hm || ctx.clock24 !== false) return hm;
    const [hh, mm] = hm.split(":").map(Number);
    return `${((hh + 11) % 12) + 1}:${pad(mm)}${hh < 12 ? "am" : "pm"}`;
  }

  const names = (list) => (list || []).map((x) => x.short || x.long).filter(Boolean).join(", ");
  const subjectOf = (l) => (l.subject || []).map((x) => x.long || x.short).filter(Boolean).join(", ")
    || l.info || (l.oldSubject || []).map((x) => x.long || x.short).join(", ") || "–";

  // Doppelstunden zusammenfassen: gleiches Fach, gleiche Lehrkraft, gleicher Raum, direkt danach
  function merge(lessons) {
    const out = [];
    for (const l of lessons) {
      const last = out[out.length - 1];
      const same = last && last.end === l.start && last.status === l.status && subjectOf(last) === subjectOf(l)
        && names(last.teacher) === names(l.teacher) && names(last.room) === names(l.room) && last.text === l.text;
      if (same) last.end = l.end;
      else out.push({ ...l });
    }
    return out;
  }

  // Ab heute die Tage, die noch etwas bringen: heute nur, solange noch Unterricht ist
  function upcomingDays(d, count) {
    const today = todayIso();
    const now = nowHm();
    return (d.days || []).filter((day) => day.date > today
      || (day.date === today && day.lessons.some((l) => l.status !== "CANCELLED" && l.end > now))).slice(0, count);
  }

  function lessonRow(l, ctx, today, now) {
    const c = ctx.config;
    const cancelled = l.status === "CANCELLED";
    const added = l.status === "ADDITIONAL" || l.status === "SUBSTITUTION";
    const changedTeacher = (l.oldTeacher || []).length > 0;
    const changedRoom = (l.oldRoom || []).length > 0;
    const changedSubject = (l.oldSubject || []).length > 0;
    const current = l.date === today && l.start <= now && now < l.end && !cancelled;
    const notes = [];
    if (cancelled) notes.push(t(TEXT.cancelled));
    else if (added) notes.push(t(TEXT.added));
    if (!cancelled && changedTeacher && c.showTeacher) notes.push(`${t(TEXT.instead)} ${esc(names(l.oldTeacher))}`);
    if (l.text) notes.push(esc(l.text));
    const teacher = c.showTeacher ? `<span class="${changedTeacher && !cancelled ? "wu-changed" : ""}">${esc(names(l.teacher))}</span>` : "";
    const room = c.showRoom ? `<span class="${changedRoom && !cancelled ? "wu-changed" : ""}">${esc(names(l.room))}</span>` : "";
    const cls = ["wu-lesson", cancelled ? "wu-cancelled" : "", current ? "wu-now" : "",
      (added || changedSubject || l.status === "CHANGED") && !cancelled ? "wu-irregular" : ""].join(" ");
    return `<tr class="${cls}">
        <td class="wu-time">${esc(clock(l.start, ctx))}</td>
        <td class="wu-subject"><span class="wu-name ${changedSubject && !cancelled ? "wu-changed" : ""}">${esc(subjectOf(l))}</span>
          ${notes.length ? `<div class="xsmall wu-note">${notes.join(" · ")}</div>` : ""}</td>
        ${c.showTeacher ? `<td class="wu-teacher">${teacher}</td>` : ""}
        ${c.showRoom ? `<td class="wu-room">${room}</td>` : ""}
      </tr>`;
  }

  function render(el, ctx) {
    const d = ctx.data;
    if (!d) { el.innerHTML = '<div class="xsmall dimmed">…</div>'; return true; }
    const h = ctx.h;
    const c = ctx.config;
    const today = todayIso();
    const now = nowHm();
    const parts = [];
    if (d.parent && d.student) parts.push(`<div class="small bright wu-student">${esc(d.student)}</div>`);

    const holiday = d.holiday && d.holiday.end >= today ? d.holiday : null;
    if (holiday) {
      const text = holiday.start <= today
        ? t(TEXT.holiday, { name: esc(holiday.name || t(TEXT.holidays)), end: shortDate(holiday.end, h) })
        : t(TEXT.holidaySoon, { name: esc(holiday.name || t(TEXT.holidays)), start: shortDate(holiday.start, h) });
      parts.push(`<div class="small wu-holiday">${text}</div>`);
    }

    const wanted = Number(c.days || 0);
    if (wanted) {
      const days = upcomingDays(d, wanted);
      if (!days.length && !holiday) parts.push(`<div class="xsmall dimmed">${esc(t(TEXT.noLessons))}</div>`);
      for (const day of days) {
        parts.push(`<div class="wu-day small">
            <div class="wu-dayname bright">${esc(dayLabel(day.date, h))}</div>
            <table class="wu-table small">${merge(day.lessons).map((l) => lessonRow(l, ctx, today, now)).join("")}</table>
          </div>`);
      }
    }

    const exams = (d.exams || []).filter((e) => e.date >= today);
    if (exams.length) {
      parts.push(`<div class="wu-section small"><div class="wu-title">${esc(t(TEXT.exams))}</div>
        <table class="wu-list">${exams.map((e) => `<tr>
          <td class="wu-when">${esc(dayLabel(e.date, h))}</td>
          <td><span class="bright">${esc(e.subject || e.name)}</span>${e.subject && e.name ? ` <span class="dimmed">· ${esc(e.name)}</span>` : ""}
            ${e.text ? `<div class="xsmall dimmed">${esc(e.text)}</div>` : ""}</td></tr>`).join("")}</table></div>`);
    }

    const homework = (d.homework || []).filter((x) => x.date >= today);
    if (homework.length) {
      parts.push(`<div class="wu-section small"><div class="wu-title">${esc(t(TEXT.homework))}</div>
        <table class="wu-list">${homework.map((x) => `<tr>
          <td class="wu-when">${esc(t(TEXT.due))} ${esc(dayLabel(x.date, h, true))}</td>
          <td><span class="bright">${esc(x.subject || "")}</span>
            ${x.text ? `<div class="xsmall wu-text">${esc(x.text).replace(/\n/g, "<br>")}</div>` : ""}</td></tr>`).join("")}</table></div>`);
    }

    if ((d.messages || []).length) {
      parts.push(`<div class="wu-section small"><div class="wu-title">${esc(t(TEXT.messages))}</div>
        ${d.messages.map((m) => `<div class="wu-message">${m.subject ? `<div class="bright">${esc(m.subject)}</div>` : ""}
          <div class="xsmall wu-text">${esc(m.text).replace(/\n/g, "<br>")}</div></div>`).join("")}</div>`);
    }

    if ((d.problems || []).length) {
      const what = d.problems.map((p) => t(TEXT[p] || { de: p })).join(", ");
      parts.push(`<div class="xsmall dimmed">${esc(t(TEXT.partly, { what }))}</div>`);
    }
    if (!parts.length) parts.push(`<div class="xsmall dimmed">${esc(t(TEXT.nothing))}</div>`);
    el.innerHTML = `<div class="wu-box">${parts.join("")}</div>`;
    el.dataset.wuMinute = now;
  }

  window.MagicFrame.register("webuntis", {
    render,
    // jede Minute: laufende Stunde markieren, nach Schulschluss weiterspringen
    tick(el, ctx) {
      if (ctx.data && el.dataset.wuMinute !== nowHm()) render(el, ctx);
    },
  });
})();
