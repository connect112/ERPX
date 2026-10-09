/** Sites that don't offer their listings to other software (LinkedIn, Naukri, Indeed): only search links, which open their own pages. */
export const JOB_SITE_TOPICS = [
  { label: "Cybersecurity freshers", query: "cyber security fresher", slug: "cyber-security-fresher" },
  { label: "DevSecOps / DevOps freshers", query: "devsecops devops fresher", slug: "devsecops-fresher" },
  { label: "Cloud freshers", query: "cloud engineer fresher", slug: "cloud-engineer-fresher" },
  { label: "SOC analyst", query: "soc analyst fresher", slug: "soc-analyst-fresher" },
  { label: "Internships", query: "cyber security intern", slug: "cyber-security-internship" },
] as const;

export function jobSiteSearchUrl(site: "linkedin" | "naukri" | "indeed", topic: (typeof JOB_SITE_TOPICS)[number]): string {
  const q = encodeURIComponent(topic.query);
  if (site === "linkedin") return `https://www.linkedin.com/jobs/search/?keywords=${q}&location=India&f_E=1%2C2`;
  if (site === "naukri") return `https://www.naukri.com/${topic.slug}-jobs`;
  return `https://in.indeed.com/jobs?q=${q}&l=India`;
}
