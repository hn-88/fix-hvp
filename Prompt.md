<!-- Private URL for my reference https://aistudio.google.com/prompts/14Bv6L5AfaOglFuUY_VJZ6F7A1cchR-FQ -->
My prompt to Gemini was as follows:
```
Currently I have a manual workflow for fixing "wiped" content due to mod_hvp update bug on moodle,
Recovering "Wiped" Activities (Data Loss)
SELECT id, name, course FROM mdl_hvp WHERE json_content LIKE '%"content":{"params":{}}}%';
SELECT json_content FROM mdl_hvp WHERE id = 30851 (or whatever) from the backed-up database
copy-paste that json_content into a text editor,
look for H5P string in the json, look for current libraries versions in the site's live database with
SELECT machine_name, major_version, minor_version
FROM mdl_hvp_libraries
WHERE machine_name IN (
'H5P.Video',
'H5P.MultiChoice',
'H5P.AdvancedText',
'H5P.InteractiveVideo',
'H5P.Column',
'H5P.Image',
'H5P.CoursePresentation'
)
ORDER BY machine_name, major_version DESC, minor_version DESC;
Manually find-replace versions like
UPDATE mdl_hvp
SET json_content = REPLACE(json_content, 'H5P.Column 1.18', 'H5P.Column 1.22'),
filtered = NULL
WHERE course = 606
AND json_content LIKE '%H5P.Column 1.18%';
Can I automate the copy-pasting of the json content from the old database backup to the live database? For specific activities like
https://our-url.com/mod/hvp/view.php?id=55555
?
```
After this ran successfully, a follow-up prompt,
```
Running the python script, I was able to get the main content of the hvp page to display. But there are images in the content which are not being displayed. Eg.
```
(I pasted the html img tag here) 
```
The image returns file not found.
```
Following the 2nd prompt, "Step 7" was added to the python script.
More information about this error
```
