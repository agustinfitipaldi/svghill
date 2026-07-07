# Deviation in driving of Austin Hill (#33) on Turn 3 — Chicagoland Speedway, eero 400
###### By Agustin Fitipaldi


# Summary
Using publicly (paid) available driver cam footage from HBO Max, I extracted per-frame MPH and RPM data from Austin Hill's and Shane van Gisbergen's in-car telemetry overlay across 7 consecutive green laps at Chicagoland, including the lap on which the cars made contact. The data shows a clear, measurable deviation from Hill's own established behavior beginning approximately half a second before contact, consistent with deliberate additional braking or throttle lift beyond what the corner required.

I verified the collision timestamp using two independent methods, both of which arrived at the same RPM/MPH combination.

# Methodology
I recorded Hill's driver cam from HBO Max and cut it into 7 clips of 8 seconds each, all synchronized to a common visual marker, the moment a fixed element of Hill's windshield intersected the watchtower at center track. I extracted one screenshot per frame at 30fps (the source framerate) and ran OCR on each to pull MPH and RPM values from the broadcast overlay.

To establish a precise collision timestamp, I used two approaches:

**Approach 1:** I recorded van Gisbergen's driver cam and identified the frame where his fender begins deforming from contact with the rear of the #33. I then counted forward to the frame where Hill's car begins veering off its normal line, 8 frames in total. Going to Hill's camera, I found the start of that same veer and counted back 8 frames to arrive at the moment of collision from Hill's perspective.

**Approach 2:** I identified the moment in SVG's camera where his front bumper passes the rightmost edge of Hill's car as it crosses perpendicular to him (Hill’s car). The gap between that reference point and the collision was 1.85 seconds. I found the same perpendicular-crossing moment in Hill's camera and counted back 1.85 seconds.

Both methods landed on the same MPH and RPM values: 156mph and 5,142 rpm. This is marked as the red "contact" line on the chart.

# What the Data Shows
Laps 41-46 cluster tightly in both speed and RPM for Hill, while varying more with SVG.

On Lap 47, we can see a sharp drop in RPM about half a second before contact, this leads to a MPH curve that is still decelerating and in the moment before impact is on a noticeably different path compared to previous laps.

For SVG we see a noticeable hang onto velocity past where he usually let off in preceding laps, which leads to a more aggressive bleed as he approaches the corner, and collides with Hill.

# Radio Context
In the roughly 15 seconds before collision, the following exchange occurred between Hill, his crew chief, and his spotter:
**Crew chief:** Seems to still be using a little bit more brake than everybody getting into 1.
**Spotter:** 34, two back to the 97, you're using more brake than everybody else getting into 1, try to work off of that.
**Hill:** Just leave me alone.
**Spotter:** Pass (?) out of line to the bottom inside bumper he's there this time, bumper, clear, clear, 3/4 to 1 now... he's gonna drive up to you — *[collision]*

With “3/4 to 1 now” occurring between the -3 and -2 second mark prior to contact.

# Limitations
This is not SMT telemetry. This is OCR-scraped data from a broadcast overlay, recorded off a streaming platform. There is inherent noise in the extraction and the synchronization of clips for the impact moment had to rely on finnicky camera perspectives.
