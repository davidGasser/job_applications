from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
import json

db = SQLAlchemy()

class SearchCriteria(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    keywords = db.Column(db.String(255), nullable=False)
    locations = db.Column(db.String(255), nullable=False)
    distance_in_km = db.Column(db.Integer, nullable=True)
    date_posted = db.Column(db.String(50), nullable=True)
    exp_level = db.Column(db.String(255), nullable=True)
    job_type = db.Column(db.String(255), nullable=True)
    pages = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now())
    is_processed = db.Column(db.Boolean, nullable=False, default=False)
    is_template = db.Column(db.Boolean, nullable=False, default=True)  # True = saved config, False = search run
    schedule_enabled = db.Column(db.Boolean, nullable=False, default=False)
    schedule_hour = db.Column(db.Integer, nullable=True)  # 0-23
    schedule_minute = db.Column(db.Integer, nullable=True, default=0)  # 0-59
    schedule_day_of_week = db.Column(db.Integer, nullable=True)  # 0-6 for weekly (Monday=0)
    schedule_day_of_month = db.Column(db.Integer, nullable=True)  # 1-31 for monthly
    last_run = db.Column(db.DateTime, nullable=True)

class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    company = db.Column(db.String(255))
    location = db.Column(db.String(255))
    description = db.Column(db.Text)
    application_link = db.Column(db.Text, unique=True)
    scraped_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = db.Column(db.String(50), nullable=False, default='New') # New, Interested, Applied, Interviewing, Offer, Rejected
    shortlisted = db.Column(db.Boolean, nullable=False, default=False)
    matching_score = db.Column(db.Float, nullable=False, default=0.0) # 0-100 percentage score (overall score)
    score_details = db.Column(db.Text, nullable=True) # JSON string with full scoring breakdown
    notes = db.Column(db.Text, nullable=True)
    interview_step = db.Column(db.Integer, nullable=True) # 1, 2, 3... for Interviewing status
    interview_stage_name = db.Column(db.String(100), nullable=True) # "Phone Screen", "Technical", etc.
    interview_chain = db.Column(db.Text, nullable=True) # JSON array of interview stages with details
    search_criteria_id = db.Column(db.Integer, db.ForeignKey('search_criteria.id'), nullable=True)
    search_criteria = db.relationship('SearchCriteria', backref=db.backref('jobs', lazy=True))
    dates = db.relationship('JobDate', backref='job', lazy=True, cascade="all, delete-orphan")
    contacts = db.relationship('Contact', backref='job', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Job {self.title} @ {self.company}>'

class Contact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    value = db.Column(db.String(255), nullable=False)

class JobDate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(255), nullable=True)
    description = db.Column(db.Text, nullable=True)

class UserProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cv_text = db.Column(db.Text, nullable=True)
    cv_filename = db.Column(db.String(255), nullable=True)
    job_preferences = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<UserProfile {self.id}>'
