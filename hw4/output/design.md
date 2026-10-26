# Campus Customs — Design Notes: Home Page Carousel (Problem 10)

## Summary

The home page banner used to show one photo: a mother and her college-bound son on campus. Campus Customs sells to a much wider group than that, so the single photo was replaced with a **carousel** that rotates through four photos. Together they show the **diversity of Yale students and the other people who might shop here**, so more visitors can see themselves in the brand.

All four images were created with the **Leonardo.AI** website. And of course, **Handsome Dan**, Yale's bulldog mascot, had to make an appearance.

## The four photos

| # | Photo | Who it speaks to |
|---|---|---|
| 1 | A mother in a "Yale Mother" quarter-zip smiling at her son in a Yale tee and cap on campus in autumn | **Families**: parents shopping for (and with) a student who is about to start at Yale |
| 2 | A group of smiling students with face paint, in Yale hoodies and tees at a football game | **Current students** of many backgrounds, and **sports fans** cheering on the Bulldogs |
| 3 | Handsome Dan in a navy Yale harness outside a shop with a blue awning | **Everyone**: a playful, instantly recognizable Yale symbol that says "this is the Yale store" |
| 4 | Three women of different ages in Yale School of Management quarter-zips and sweaters, talking at a table | **Graduate and professional students, alumni and staff**, showing that Yale apparel isn't only for undergraduates |

## Why a carousel

- **A broader audience:** different ages, backgrounds and roles (parents, undergraduates, graduate students, alumni, fans) each see someone like themselves within a few seconds of landing on the site.
- **It matches what the store sells:** the catalogue covers residential colleges, graduate and professional schools, varsity sports and "Yale family" designs (Mom, Dad, Grandpa…). The photos reflect that range.
- **Personality:** Handsome Dan adds warmth and humor, which matches the shop assistant's playful sold-out jokes.
- **No extra clutter:** the carousel replaces the single photo in the same space, so the headline and the **Shop products** and **Create account** buttons stay where shoppers expect them.

## Design details

- **Yale look:** the headline sits on a Yale Blue panel (`#00356B`) at the left, with the photo on the right. The controls use white on Yale Blue, matching the rest of the site.
- **Movement:**
  - each photo shows for 6 seconds and gently cross-fades into the next;
  - it waits while a visitor's pointer is over the photos or they're using its buttons.
- **Controls:**
  - previous/next arrows;
  - a dot for each photo;
  - a pause/play button.
- **Accessibility:**
  - each photo has a written description for screen-reader users;
  - the carousel doesn't move on its own for visitors whose device asks for reduced motion;
  - the pause button lets anyone stop the movement.
- **Faces stay in view:** each photo has its own crop point, so faces aren't cut off on laptops and large monitors. On phones, the whole photo shows above the headline.
- **Clean edges:** one Leonardo.AI image came out as a square file with white bars above and below the picture. A small script, `trim_carousel_images.py`, trimmed the bars so the banner shows no white strips. The original is saved in `images/originals/`.
- **Easy to update:** the carousel shows every `.jpg` in `hw4/images/`, so new seasonal or event photos can be added without changing any code.

## A note on accuracy

The photos are AI-generated illustrations of the Campus Customs style, not product shots. Some clothing in them (for example the "Yale Mother" quarter-zip or the SOM quarter-zips) may not exactly match items in the catalogue. Shoppers get true product details, prices and stock from the Product pages and the shop assistant, which answers only from the catalogue database.
