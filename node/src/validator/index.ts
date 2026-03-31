/**
 * brain.ctx schema validator for Node.js — uses AJV with shared JSON Schema.
 */

import * as fs   from "fs"
import * as path from "path"
import { createRequire } from "module"
import { fileURLToPath } from "url"

const require     = createRequire(import.meta.url)
const __dirname   = path.dirname(fileURLToPath(import.meta.url))
const SCHEMA_PATH = path.resolve(__dirname, "../spec/brain-ctx.schema.json")
const DEV_SCHEMA  = path.resolve(__dirname, "../../../../spec/brain-ctx.schema.json")

import type { BrainCtxFile } from "../types/index.js"

let _validate: ((data: unknown) => boolean) & { errors?: unknown[] } | null = null

function getValidator() {
  if (_validate) return _validate
  const Ajv        = require("ajv")
  const addFormats = require("ajv-formats")
  const ajv        = new Ajv({ allErrors: true, strict: false })
  addFormats(ajv)

  for (const p of [SCHEMA_PATH, DEV_SCHEMA]) {
    if (fs.existsSync(p)) {
      const schema = JSON.parse(fs.readFileSync(p, "utf-8"))
      _validate = ajv.compile(schema)
      return _validate!
    }
  }

  _validate = ajv.compile({
    type: "object", required: ["version","identity"],
    properties: {
      version:  { type: "string" },
      identity: { type: "object", required: ["name"],
                  properties: { name: { type: "string" } } },
    },
  })
  return _validate!
}

export interface ValidationResult {
  valid:  boolean
  errors: string[]
}

export function validateBrainCtx(data: unknown): ValidationResult {
  const validate = getValidator()
  const valid    = validate(data)
  if (valid) return { valid: true, errors: [] }
  const errors = ((validate.errors ?? []) as Array<{instancePath: string; message?: string}>)
    .map(e => `[${e.instancePath || "root"}] ${e.message}`)
  return { valid: false, errors }
}

export function validateBrainCtxFile(filePath: string): ValidationResult {
  try {
    const yaml = require("js-yaml")
    if (!fs.existsSync(filePath)) return { valid: false, errors: [`File not found: ${filePath}`] }
    const data = yaml.load(fs.readFileSync(filePath, "utf-8"))
    return validateBrainCtx(data)
  } catch (e) {
    return { valid: false, errors: [`Parse error: ${(e as Error).message}`] }
  }
}

export function isBrainCtxFile(data: unknown): data is BrainCtxFile {
  return (
    typeof data === "object" && data !== null &&
    "version" in data && "identity" in data &&
    typeof (data as BrainCtxFile).identity?.name === "string"
  )
}
