# art5 — ADD_ONLY

- Change-type guess: `ADD` (human must confirm per framework §2)
- Title: 'Prohibited AI practices' → 'Prohibited AI practices'
- Pages: [51, 52, 53] → [13, 14, 15, 16, 17]

## Added

> (ba) the placing on the market, the putting into service or the use of an AI system that generates or manipulates realistic images, videos, audio or similar material of an identifiable natural person’s intimate parts, or of an identifiable natural person engaged in sexually explicit activities, without that person’s freely-given, specific, informed, unambiguous and explicit consent for that generation or manipulation;

> (bb) the placing on the market, the putting into service or the use of an AI system that generates or manipulates material or performance within the meaning of Article 2, points (c) and (e), of Directive 2011/93/EU, except where a ‘without right’ defence applies under national law;

> 1a. For the purposes of paragraph 1, first subparagraph, points (ba) and (bb):

> (a) the placing on the market or putting into service of an AI system that generates or manipulates the material or performance referred to in paragraph 1, first subparagraph, point (ba) or (bb) is only prohibited where:

> (i) that generation or manipulation is the intended purpose of the AI system; or

> (ii) the system’s design, training, architecture, capabilities or user-facing functionalities make that generation or manipulation a reasonably foreseeable and reproducible outcome, without requiring significant technical modification, and the system does not have reasonable and adequate technical safety measures and other safeguards to reliably prevent that generation or manipulation, taking into account reasonably foreseeable misuse, and to correct observed or reported misuse;

> (b) the use of an AI system that generates or manipulates the material or performance referred to in paragraph 1, first subparagraph, points (ba) and (bb) is only prohibited where the deployer uses the system for the purpose of generating or manipulating such material or performance.

> 1b. For the purposes of paragraph 1, first subparagraph, point (ba), an AI system that manipulates material in a way that does not increase the exposure of any depicted intimate parts or alter the nature of any depicted sexually explicit activities shall not constitute manipulation.

## Unified diff (provision units)

```diff
--- art5@from
+++ art5@to
@@ -3,2 +3,4 @@
 (b) the placing on the market, the putting into service or the use of an AI system that exploits any of the vulnerabilities of a natural person or a specific group of persons due to their age, disability or a specific social or economic situation, with the objective, or the effect, of materially distorting the behaviour of that person or a person belonging to that group in a manner that causes or is reasonably likely to cause that person or another person significant harm;
+(ba) the placing on the market, the putting into service or the use of an AI system that generates or manipulates realistic images, videos, audio or similar material of an identifiable natural person’s intimate parts, or of an identifiable natural person engaged in sexually explicit activities, without that person’s freely-given, specific, informed, unambiguous and explicit consent for that generation or manipulation;
+(bb) the placing on the market, the putting into service or the use of an AI system that generates or manipulates material or performance within the meaning of Article 2, points (c) and (e), of Directive 2011/93/EU, except where a ‘without right’ defence applies under national law;
 (c) the placing on the market, the putting into service or the use of AI systems for the evaluation or classification of natural persons or groups of persons over a certain period of time based on their social behaviour or known, inferred or predicted personal or personality characteristics, with the social score leading to either or both of the following:
@@ -14,2 +16,8 @@
 (iii) the localisation or identification of a person suspected of having committed a criminal offence, for the purpose of conducting a criminal investigation or prosecution or executing a criminal penalty for offences referred to in Annex II and punishable in the Member State concerned by a custodial sentence or a detention order for a maximum period of at least four years. Point (h) of the first subparagraph is without prejudice to Article 9 of Regulation (EU) 2016/679 for the processing of biometric data for purposes other than law enforcement.
+1a. For the purposes of paragraph 1, first subparagraph, points (ba) and (bb):
+(a) the placing on the market or putting into service of an AI system that generates or manipulates the material or performance referred to in paragraph 1, first subparagraph, point (ba) or (bb) is only prohibited where:
+(i) that generation or manipulation is the intended purpose of the AI system; or
+(ii) the system’s design, training, architecture, capabilities or user-facing functionalities make that generation or manipulation a reasonably foreseeable and reproducible outcome, without requiring significant technical modification, and the system does not have reasonable and adequate technical safety measures and other safeguards to reliably prevent that generation or manipulation, taking into account reasonably foreseeable misuse, and to correct observed or reported misuse;
+(b) the use of an AI system that generates or manipulates the material or performance referred to in paragraph 1, first subparagraph, points (ba) and (bb) is only prohibited where the deployer uses the system for the purpose of generating or manipulating such material or performance.
+1b. For the purposes of paragraph 1, first subparagraph, point (ba), an AI system that manipulates material in a way that does not increase the exposure of any depicted intimate parts or alter the nature of any depicted sexually explicit activities shall not constitute manipulation.
 2. The use of ‘real-time’ remote biometric identification systems in publicly accessible spaces for the purposes of law enforcement for any of the objectives referred to in paragraph 1, first subparagraph, point (h), shall be deployed for the purposes set out in that point only to confirm the identity of the specifically targeted individual, and it shall take into account the following elements:
```
