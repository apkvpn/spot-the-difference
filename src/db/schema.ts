import { integer, jsonb, pgTable, text, timestamp } from "drizzle-orm/pg-core";

export const jobs = pgTable("sd_jobs", {
  id: text("id").primaryKey(),
  title: text("title").notNull(),
  status: text("status").notNull().default("queued"),
  progress: integer("progress").notNull().default(0),
  stage: text("stage").notNull().default(""),
  settings: jsonb("settings").notNull(),
  report: jsonb("report"),
  error: text("error"),
  pid: integer("pid"),
  createdAt: timestamp("created_at").notNull().defaultNow(),
  updatedAt: timestamp("updated_at").notNull().defaultNow(),
});

export type Job = typeof jobs.$inferSelect;
