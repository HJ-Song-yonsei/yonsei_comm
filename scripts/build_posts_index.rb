#!/usr/bin/env ruby
# frozen_string_literal: true

require "json"
require "yaml"
require "date"

POST_DIR = "data/posts"
OUT_FILE = "data/posts.json"

def parse_frontmatter(text)
  return [{}, text] unless text.start_with?("---\n") || text.start_with?("---\r\n")

  if text =~ /\A---\s*\r?\n(.*?)\r?\n---\s*\r?\n/m
    fm_raw = Regexp.last_match(1)
    body   = text.sub(/\A---\s*\r?\n.*?\r?\n---\s*\r?\n/m, "")
    fm = YAML.safe_load(fm_raw, permitted_classes: [Date], aliases: true) || {}
    [fm, body]
  else
    [{}, text]
  end
end

def normalize_date(v, fallback: nil)
  return fallback if v.nil? || v.to_s.strip.empty?

  if v.is_a?(Date)
    v.strftime("%Y-%m-%d")
  else
    Date.parse(v.to_s).strftime("%Y-%m-%d")
  end
rescue
  fallback
end

posts = []

Dir.glob(File.join(POST_DIR, "*.{md,markdown,html}")).sort.each do |path|
  filename = File.basename(path)
  stem = File.basename(path, File.extname(path))

  text = File.read(path, mode: "r:BOM|UTF-8")
  fm, _body = parse_frontmatter(text)

  # 기본값
  title  = (fm["title"]  || "").to_s
  author = (fm["author"] || "").to_s
  notice = (fm["notice"] || "일반").to_s.strip

  file_attachment = fm["file_attachment"]
  file_attachment = [] unless file_attachment.is_a?(Array)

  mtime_fallback = File.mtime(path).to_date.strftime("%Y-%m-%d")
  date = normalize_date(fm["date"], fallback: mtime_fallback)

  posts << {
    "id" => stem,                 # URL ?id= 로 쓰기 좋은 안정적 id
    "notice" => notice,
    "title" => title,
    "author" => author,
    "date" => date,
    "contentfile" => filename,    # notice.html이 data/posts/ 아래에서 fetch
    "file_attachment" => file_attachment
  }
end

def date_key(s)
  Date.parse(s.to_s)
rescue
  Date.new(1970, 1, 1)
end

# 정렬: 공지 먼저, 그 다음 날짜 내림차순
posts.sort_by! do |p|
  pinned = (p["notice"].to_s.strip == "공지") ? 0 : 1
  [pinned, -date_key(p["date"]).jd, p["id"].to_s]
end

File.write(OUT_FILE, JSON.pretty_generate(posts) + "\n")
puts "Wrote #{OUT_FILE} (#{posts.length} posts)"
