const ALL_COMMANDS = [
  { name: '/search', desc: 'DuckDuckGo search' },
  { name: '/research', desc: 'Full deep research pipeline' },
  { name: '/news', desc: 'Latest news via RSS' },
  { name: '/wiki', desc: 'Wikipedia summary' },
  { name: '/academic', desc: 'Search academic papers' },
  { name: '/wayback', desc: 'Internet Archive snapshots' },
  { name: '/whois', desc: 'WHOIS domain lookup' },
  { name: '/dns', desc: 'DNS records lookup' },
  { name: '/headers', desc: 'HTTP headers fingerprint' },
  { name: '/iplookup', desc: 'IP geolocation + ASN' },
  { name: '/subdomains', desc: 'Subdomain enumeration' },
  { name: '/shodan', desc: 'Shodan InternetDB lookup' },
  { name: '/exif', desc: 'Dump EXIF of current image' },
  { name: '/hash', desc: 'Hash current image' },
  { name: '/ela', desc: 'Error Level Analysis' },
  { name: '/faces', desc: 'Face detection summary' },
  { name: '/geoguess', desc: 'AI geolocation estimate' },
  { name: '/translate', desc: 'Detect language and translate' },
  { name: '/summarize', desc: 'Fetch and summarize a webpage' },
  { name: '/model', desc: 'Switch AI model' },
  { name: '/clear', desc: 'Clear chat history' },
  { name: '/help', desc: 'Show all commands' },
]

export function SlashCommandMenu({ query, onSelect }) {
  const filtered = ALL_COMMANDS.filter(c =>
    c.name.slice(1).startsWith(query.toLowerCase()) || c.desc.toLowerCase().includes(query.toLowerCase())
  ).slice(0, 8)

  if (!filtered.length) return null

  return (
    <div className="mx-4 mb-1 card border border-border-color rounded-lg overflow-hidden">
      {filtered.map((cmd) => (
        <button
          key={cmd.name}
          onClick={() => onSelect(cmd.name)}
          className="w-full flex items-center gap-3 px-3 py-2 hover:bg-accent-cyan/5 text-left transition-colors"
        >
          <span className="mono text-accent-green text-sm font-semibold">{cmd.name}</span>
          <span className="text-xs text-text-dim">{cmd.desc}</span>
        </button>
      ))}
    </div>
  )
}
