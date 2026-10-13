/**
 * The text of the public Privacy Policy and Data Deletion pages. Written to match what the system actually does; if the system
 * changes (what is collected, who it is shared with, how long it is kept), change this text in the same pull request.
 */

export const COMPANY = "GIR Technologies (Pentrix)";
export const CONTACT_EMAIL = "info@girtechnologies.com";
export const SITE = "erp.pentrix.in";
export const INSTAGRAM_ACCOUNT = "@pentrix16";
export const POLICY_UPDATED = "13 October 2026";
export const DELETION_DAYS = 30;

export interface Section {
  heading: string;
  paragraphs?: string[];
  items?: string[];
}

export interface LegalDocument {
  title: string;
  updated: string;
  intro: string;
  sections: Section[];
}

export const PRIVACY_POLICY: LegalDocument = {
  title: "Privacy Policy",
  updated: POLICY_UPDATED,
  intro: `${COMPANY} ("we", "us") runs the Pentrix training platform at ${SITE} and the Instagram account ${INSTAGRAM_ACCOUNT}. This policy explains what personal information we handle, why, who sees it, how long we keep it, and what you can ask us to do.`,
  sections: [
    {
      heading: "What this policy covers",
      paragraphs: [
        `It covers the ${SITE} platform (enquiries, admissions, courses, learning and our internal tools) and the way our team uses Instagram's official platform to manage the ${INSTAGRAM_ACCOUNT} account: publishing posts, reading and answering comments and messages, and viewing insights.`,
        "Our Instagram integration is used only by our own team, for our own account. It is not an app that other people log in to.",
      ],
    },
    {
      heading: "Information we collect",
      items: [
        "Information you give us: your name, email address, phone number and the course you ask about when you enquire, enrol or use our platform.",
        `Instagram comments and direct messages sent to ${INSTAGRAM_ACCOUNT}: the text, the sender's public username, and the time. Replies written by our team are also recorded.`,
        `Information about ${INSTAGRAM_ACCOUNT} itself: our posts, and the follower counts and engagement figures Instagram reports for the account. These are totals, not information about individual people.`,
        "Link opens: if you open one of our short links we count one visit for that day. We do not record your address, device or identity.",
        "If a team member decides your message is a genuine enquiry, we create a lead containing your name, your Instagram username and the contact details you gave us, and the course you asked about.",
      ],
    },
    {
      heading: "How we use it",
      items: [
        "To answer your comments, messages and enquiries and to tell you about our courses when you ask.",
        "To run and improve our social media and measure which posts are useful, using totals and counts.",
        "To keep our platform secure and to meet our legal obligations.",
      ],
      paragraphs: [
        "A person on our team reads and sends every reply. Nothing is answered automatically.",
        "We use an AI service to help our staff: the text of a comment or message may be sent to our AI provider so it can summarise it and suggest a draft reply. Staff always review the draft and decide whether to send anything. We do not use your messages to train AI models, and we do not sell personal information.",
      ],
    },
    {
      heading: "Who we share it with",
      items: [
        "Meta (Instagram), whose platform delivers the messages and comments to us.",
        "Service providers that help us run the platform: cloud hosting, email delivery and the AI service described above. They may only use the information to provide their service to us.",
        "Authorities, where the law requires it.",
      ],
      paragraphs: ["We do not sell personal information."],
    },
    {
      heading: "How long we keep it",
      paragraphs: [
        "Instagram comments, messages and the text of our replies are deleted automatically after the retention period we have set (365 days unless we change it). A record that a reply was sent, by whom and when, is kept without its text.",
        "Leads and admissions records in our CRM are kept for as long as we need them to deal with your enquiry or admission, and then deleted or anonymised.",
      ],
    },
    {
      heading: "Security",
      paragraphs: [
        "Our Instagram access token is stored encrypted and is never shown in the platform. Access to comments, messages and leads is limited to staff who need it, and changes are recorded in an audit log that does not contain the text of messages.",
      ],
    },
    {
      heading: "Your choices and rights",
      items: [
        "Ask what we hold about you, ask us to correct it, or ask us to delete it.",
        "Stop using our Instagram messaging at any time: you can block or stop messaging the account.",
        "Remove any app access in Instagram under Settings, Apps and websites.",
      ],
      paragraphs: [
        `To ask for deletion, follow the steps on our Data Deletion page (https://${SITE}/data-deletion) or email ${CONTACT_EMAIL}. We handle personal information in line with the laws that apply to us in India.`,
      ],
    },
    {
      heading: "Children",
      paragraphs: ["Our services are not directed at children under 13, and we do not knowingly collect their personal information."],
    },
    {
      heading: "Changes to this policy",
      paragraphs: ["If we change this policy we will update the date at the top of this page. If a change is significant we will tell you in a clear way."],
    },
    {
      heading: "Contact us",
      paragraphs: [`${COMPANY}. Email: ${CONTACT_EMAIL}.`],
    },
  ],
};

export const DATA_DELETION: LegalDocument = {
  title: "Data Deletion",
  updated: POLICY_UPDATED,
  intro: `You can ask ${COMPANY} to delete the personal information we hold about you, including anything from your Instagram comments and messages to ${INSTAGRAM_ACCOUNT}.`,
  sections: [
    {
      heading: "How to ask",
      items: [
        `Email ${CONTACT_EMAIL} with the subject "Delete my data".`,
        "Tell us your Instagram username (and your name and email if you also gave them to us), so we can find your records.",
        "We may ask you to confirm you are the owner of the account, for example by messaging us from it.",
      ],
    },
    {
      heading: "What we delete",
      items: [
        "Your comments and your direct-message conversations with us, and the text of our replies to them.",
        "Your Instagram username in our records.",
        "Your lead or admissions record, on request, unless we must keep part of it to meet a legal or accounting obligation. We will tell you if that applies.",
      ],
    },
    {
      heading: "How long it takes",
      paragraphs: [`We complete deletion within ${DELETION_DAYS} days of confirming your request and tell you by email when it is done.`],
    },
    {
      heading: "Removing app access on Instagram",
      paragraphs: ["You can also remove any app's access to your account yourself: in Instagram go to Settings, then Apps and websites, and remove it."],
    },
    {
      heading: "Questions",
      paragraphs: [`Write to ${CONTACT_EMAIL}. Our full Privacy Policy is at https://${SITE}/privacy.`],
    },
  ],
};
