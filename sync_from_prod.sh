#!/bin/bash
rsync -av kelvin@kelvin.cs.vsb.cz:kelvin/{db.sqlite3,submits,tasks} . 
rsync -av kelvin@kelvin.cs.vsb.cz:kelvin/survey/surveys survey/
